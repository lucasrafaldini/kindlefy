from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
from typing import Any, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from kindlefy_engine.compiler.epub_builder import build_epub, validate_epub_archive
from kindlefy_engine.compiler.mobi_builder import build_mobi
from kindlefy_engine.compiler.typography import generate_kindle_css, render_chapter_xhtml
from kindlefy_engine.demo_samples import create_torture_test_pdf
from kindlefy_engine.harness.model_manager import GemmaModelManager, get_app_data_dir
from kindlefy_engine.harness.orchestrator import HarnessOrchestrator
from kindlefy_engine.models import BookMetadata, StructuredBook

app = FastAPI(
    title="Kindlefy Engine & Gemma 2 2B Harness API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_manager = GemmaModelManager()
orchestrator = HarnessOrchestrator(model_manager=model_manager)

# Store recent conversion sessions in memory + disk output folder
SESSIONS: dict[str, dict[str, Any]] = {}
JOBS: dict[str, dict[str, Any]] = {}


def _set_job_progress(job_id: str, stage: str, percent: int, msg: str) -> None:
    step_idx = 0
    if stage == "pass1":
        step_idx = 1
    elif stage == "pass2":
        step_idx = 2
    elif stage == "pass3":
        step_idx = 3
    elif stage in {"pass4", "compile", "done"}:
        step_idx = 4

    JOBS[job_id] = {
        "job_id": job_id,
        "status": "completed" if stage == "done" else "processing",
        "stage": stage,
        "percent": percent,
        "step_index": step_idx,
        "message": msg,
        "error": None,
    }


class ConvertPathRequest(BaseModel):
    file_path: str
    title: str = "Livro Sem Título"
    author: str = "Autor Desconhecido"
    language: str = "pt-BR"
    theme: str = "classic"
    enable_drop_caps: bool = True
    justify_text: bool = True
    use_llm_harness: bool = True
    force_ocr: bool = False


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "engine": "kindlefy-engine",
        "version": "0.1.0",
        "model": model_manager.get_status(),
    }


@app.get("/api/model/status")
def get_model_status() -> dict[str, Any]:
    return model_manager.get_status()


@app.get("/api/model/scan-local")
def scan_local_models() -> dict[str, Any]:
    models = model_manager.scan_system_for_models()
    return {"found_models": models}


class SetModelPathRequest(BaseModel):
    path: str


@app.post("/api/model/set-path")
def set_model_path(req: SetModelPathRequest) -> dict[str, Any]:
    success = model_manager.set_custom_path(req.path)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Arquivo de modelo não encontrado ou menor que 100MB.",
        )
    return model_manager.get_status()


@app.post("/api/model/select/{model_id}")
def select_model(model_id: str) -> dict[str, Any]:
    global model_manager, orchestrator
    model_manager = GemmaModelManager(model_id=model_id)
    orchestrator = HarnessOrchestrator(model_manager=model_manager)
    return model_manager.get_status()


@app.post("/api/model/download")
async def start_model_download() -> dict[str, Any]:
    if not model_manager.download_state["downloading"] and not model_manager.is_model_installed():
        asyncio.create_task(model_manager.download_model())
    return model_manager.get_status()


@app.get("/api/benchmarks/samples")
def list_benchmark_samples() -> dict[str, Any]:
    hidden_dir = Path.home() / ".kindlefy" / "benchmarks"
    hidden_dir.mkdir(parents=True, exist_ok=True)
    app_bench_dir = get_app_data_dir() / "benchmarks"
    app_bench_dir.mkdir(parents=True, exist_ok=True)

    target_dir = hidden_dir if any(hidden_dir.glob("*.pdf")) else app_bench_dir
    samples = []
    for p in sorted(target_dir.glob("*.pdf")):
        samples.append({
            "filename": p.name,
            "path": str(p),
            "size_kb": round(p.stat().st_size / 1024, 1),
        })
    return {
        "benchmark_dir": str(target_dir),
        "samples": samples,
    }


def _compile_and_store_book(
    book: StructuredBook,
    base_stem: str,
    progress_cb: Optional[Any] = None,
) -> dict[str, Any]:
    if progress_cb:
        progress_cb("compile", 96, "Compilando XHTML, regras de CSS Kindle e gerando EPUB 3 & MOBI...")

    out_dir = get_app_data_dir() / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_stem).strip("_") or "kindlefy_book"

    epub_path = out_dir / f"{safe_stem}.epub"
    mobi_path = out_dir / f"{safe_stem}.mobi"

    build_epub(book, epub_path)
    epub_validation = validate_epub_archive(epub_path)
    build_mobi(book, mobi_path, epub_path=epub_path)

    chapter_previews = [
        {
            "chapter_id": ch.chapter_id,
            "number": ch.number,
            "title": ch.title,
            "subtitle": ch.subtitle,
            "paragraph_count": len(ch.blocks),
            "xhtml": render_chapter_xhtml(ch, book.metadata),
        }
        for ch in book.chapters
    ]

    result = {
        "session_id": safe_stem,
        "book": book.model_dump(),
        "css": generate_kindle_css(book.metadata),
        "chapter_previews": chapter_previews,
        "exports": {
            "epub_path": str(epub_path),
            "epub_size_kb": round(epub_path.stat().st_size / 1024, 1),
            "epub_validation": epub_validation,
            "mobi_path": str(mobi_path),
            "mobi_size_kb": round(mobi_path.stat().st_size / 1024, 1),
        },
    }
    SESSIONS[safe_stem] = result

    if progress_cb:
        progress_cb("done", 100, "Livro formatado e validado com sucesso!")

    return result


@app.get("/api/convert/job/{job_id}")
def get_job_progress(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        return {
            "job_id": job_id,
            "status": "not_found",
            "percent": 0,
            "step_index": 0,
            "stage": "init",
            "message": "Aguardando início do trabalho...",
            "error": None,
        }
    return job


@app.post("/api/convert/upload")
async def convert_uploaded_file(
    file: UploadFile = File(...),
    title: str = Form("Livro Sem Título"),
    author: str = Form("Autor Desconhecido"),
    language: str = Form("auto"),
    document_profile: str = Form("auto"),
    theme: str = Form("classic"),
    enable_drop_caps: bool = Form(True),
    justify_text: bool = Form(True),
    use_llm_harness: bool = Form(True),
    force_ocr: bool = Form(False),
    job_id: Optional[str] = Form(None),
) -> dict[str, Any]:
    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    stem = Path(file.filename or "livro").stem

    if job_id:
        _set_job_progress(job_id, "ingest", 8, "Lendo documento e extraindo geometria textual...")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    cb = (lambda st, pct, m: _set_job_progress(job_id, st, pct, m)) if job_id else None

    try:
        effective_title = title if title != "Livro Sem Título" else stem.replace("_", " ").replace("-", " ").title()
        meta = BookMetadata(
            title=effective_title,
            author=author,
            language=language,
            document_profile=document_profile,
            theme=theme,
            enable_drop_caps=enable_drop_caps,
            justify_text=justify_text,
            use_llm_harness=use_llm_harness,
            force_ocr=force_ocr,
        )
        book = orchestrator.process_file(str(tmp_path), metadata=meta, progress_cb=cb)
        res = _compile_and_store_book(book, stem, progress_cb=cb)
        if job_id and job_id in JOBS:
            JOBS[job_id]["result"] = res
        return res
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        print(f"[ERROR] Erro durante a conversão: {e}\n{tb_str}")
        if job_id:
            JOBS[job_id] = {
                "job_id": job_id,
                "status": "error",
                "stage": "error",
                "percent": 0,
                "step_index": 0,
                "message": f"Erro durante a conversão: {str(e)}",
                "error": str(e),
                "traceback": tb_str,
            }
        raise HTTPException(
            status_code=500,
            detail={
                "message": str(e),
                "traceback": tb_str,
            },
        )
    finally:
        tmp_path.unlink(missing_ok=True)


class ConvertLocalPathRequest(BaseModel):
    file_path: str
    title: str = "Livro Sem Título"
    author: str = "Autor Desconhecido"
    language: str = "auto"
    document_profile: str = "auto"
    theme: str = "classic"
    enable_drop_caps: bool = True
    justify_text: bool = True
    use_llm_harness: bool = True
    force_ocr: bool = False
    job_id: Optional[str] = None


@app.post("/api/convert/local-path")
def convert_local_path(req: ConvertLocalPathRequest) -> dict[str, Any]:
    raw = req.file_path.strip()
    if raw.startswith("file://"):
        from urllib.parse import unquote, urlparse
        raw = unquote(urlparse(raw).path)
    else:
        from urllib.parse import unquote
        raw = unquote(raw)

    target_path = Path(raw).expanduser().resolve()
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=400, detail=f"Arquivo não encontrado no disco: {target_path}")

    stem = target_path.stem
    if req.job_id:
        _set_job_progress(req.job_id, "ingest", 8, "Lendo documento e extraindo geometria textual...")

    cb = (lambda st, pct, m: _set_job_progress(req.job_id, st, pct, m)) if req.job_id else None

    try:
        effective_title = (
            req.title
            if req.title != "Livro Sem Título"
            else stem.replace("_", " ").replace("-", " ").title()
        )
        meta = BookMetadata(
            title=effective_title,
            author=req.author,
            language=req.language,
            document_profile=req.document_profile,
            theme=req.theme,
            enable_drop_caps=req.enable_drop_caps,
            justify_text=req.justify_text,
            use_llm_harness=req.use_llm_harness,
            force_ocr=req.force_ocr,
        )
        book = orchestrator.process_file(str(target_path), metadata=meta, progress_cb=cb)
        res = _compile_and_store_book(book, stem, progress_cb=cb)
        if req.job_id and req.job_id in JOBS:
            JOBS[req.job_id]["result"] = res
        return res
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        print(f"[ERROR] Erro durante a conversão (local-path): {e}\n{tb_str}")
        if req.job_id:
            JOBS[req.job_id] = {
                "job_id": req.job_id,
                "status": "error",
                "stage": "error",
                "percent": 0,
                "step_index": 0,
                "message": f"Erro durante a conversão: {str(e)}",
                "error": str(e),
                "traceback": tb_str,
            }
        raise HTTPException(
            status_code=500,
            detail={
                "message": str(e),
                "traceback": tb_str,
            },
        )


@app.post("/api/convert/demo-torture-pdf")
def run_demo_torture_pdf(
    theme: str = "classic",
    enable_drop_caps: bool = True,
    justify_text: bool = True,
    use_llm_harness: bool = True,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generates and converts a complex multi-page PDF containing multi-column reflow,
    broken line wraps, hyphenated words, running headers/footers, and OCR artifacts.
    """
    sample_dir = get_app_data_dir() / "samples"
    pdf_path = create_torture_test_pdf(sample_dir / "cronicas_horizonte_torture_test.pdf")
    meta = BookMetadata(
        title="Crônicas do Horizonte Perdido",
        author="Mestre Tipógrafo",
        language="pt-BR",
        theme=theme,
        enable_drop_caps=enable_drop_caps,
        justify_text=justify_text,
        use_llm_harness=use_llm_harness,
    )

    cb = (lambda st, pct, m: _set_job_progress(job_id, st, pct, m)) if job_id else None

    if job_id:
        _set_job_progress(job_id, "ingest", 10, "Iniciando PDF de teste multi-colunas e OCR...")

    try:
        book = orchestrator.process_file(str(pdf_path), metadata=meta, progress_cb=cb)
        res = _compile_and_store_book(book, "cronicas_horizonte_perdido", progress_cb=cb)
        res["source_pdf_path"] = str(pdf_path)
        if job_id and job_id in JOBS:
            JOBS[job_id]["result"] = res
        return res
    except Exception as e:
        if job_id:
            JOBS[job_id] = {
                "job_id": job_id,
                "status": "error",
                "stage": "error",
                "percent": 0,
                "step_index": 0,
                "message": f"Erro no demo torture: {str(e)}",
                "error": str(e),
            }
        raise


@app.get("/api/export/download/{session_id}/{fmt}")
def download_export(session_id: str, fmt: str) -> FileResponse:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão de exportação não encontrada.")

    if fmt == "epub":
        file_path = Path(session["exports"]["epub_path"])
        media_type = "application/epub+zip"
    elif fmt == "mobi":
        file_path = Path(session["exports"]["mobi_path"])
        media_type = "application/x-mobipocket-ebook"
    else:
        raise HTTPException(status_code=400, detail="Formato inválido. Use 'epub' ou 'mobi'.")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo exportado não encontrado no disco.")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )
