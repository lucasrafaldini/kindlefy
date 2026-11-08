from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import uvicorn

from kindlefy_engine.compiler.epub_builder import build_epub
from kindlefy_engine.compiler.mobi_builder import build_mobi
from kindlefy_engine.demo_samples import create_torture_test_pdf
from kindlefy_engine.harness.model_manager import GemmaModelManager
from kindlefy_engine.harness.orchestrator import HarnessOrchestrator
from kindlefy_engine.models import BookMetadata


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kindlefy-engine",
        description="Kindlefy Core Engine & Assistente de Formatação e Contexto (PDF/TXT/DOCX/MD -> EPUB 3 & MOBI)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # 1. serve command
    serve_p = sub.add_parser("serve", help="Inicia o servidor sidecar HTTP local para a UI Desktop (Tauri).")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8765)

    # 2. convert command
    conv_p = sub.add_parser("convert", help="Converte qualquer arquivo para EPUB 3 e MOBI com o Harness Gemma 2.")
    conv_p.add_argument("input", help="Caminho para o arquivo de entrada (.pdf, .txt, .md, .docx, .html, .epub)")
    conv_p.add_argument("-o", "--output-dir", default=".", help="Diretório de saída para .epub e .mobi")
    conv_p.add_argument("--title", default="Livro Sem Título")
    conv_p.add_argument("--author", default="Autor Desconhecido")
    conv_p.add_argument("--theme", choices=["classic", "modern", "academic"], default="classic")
    conv_p.add_argument("--ocr", action="store_true", help="Força a execução de OCR mesmo se o PDF contiver texto nativo")
    conv_p.add_argument("--no-llm", action="store_true", help="Desativa os passes do Gemma 2 2B Harness")

    # 3. model command
    mod_p = sub.add_parser("model", help="Gerencia o modelo local Gemma 2 2B GGUF.")
    mod_p.add_argument("action", choices=["status", "download"], help="Ação sobre o modelo local")

    # 4. torture-test command
    tt_p = sub.add_parser("torture-test", help="Gera um PDF complexo de teste e executa o pipeline completo.")
    tt_p.add_argument("-o", "--output-dir", default="./exports_demo")

    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run("kindlefy_engine.server:app", host=args.host, port=args.port, log_level="info")
        return

    if args.command == "model":
        mgr = GemmaModelManager()
        if args.action == "status":
            print(json.dumps(mgr.get_status(), indent=2, ensure_ascii=False))
        elif args.action == "download":
            def _cb(pct: float, dl: float, tot: float) -> None:
                print(f"\rBaixando {mgr.model_info['filename']}: {pct:5.1f}% ({dl:.1f}/{tot:.1f} MB)", end="", flush=True)

            path = asyncio.run(mgr.download_model(progress_callback=_cb))
            print(f"\nModelo instalado com sucesso em: {path}")
        return

    if args.command == "torture-test":
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = create_torture_test_pdf(out_dir / "torture_input.pdf")
        orch = HarnessOrchestrator()
        meta = BookMetadata(title="Crônicas do Horizonte Perdido", author="Mestre Tipógrafo")
        book = orch.process_file(str(pdf_path), metadata=meta)
        epub_p = build_epub(book, out_dir / "cronicas_horizonte.epub")
        mobi_p = build_mobi(book, out_dir / "cronicas_horizonte.mobi", epub_path=epub_p)
        print(json.dumps({
            "source_pdf": str(pdf_path),
            "epub": str(epub_p),
            "mobi": str(mobi_p),
            "stats": book.stats.model_dump(),
        }, indent=2, ensure_ascii=False))
        return

    if args.command == "convert":
        in_path = Path(args.input)
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        title = args.title if args.title != "Livro Sem Título" else in_path.stem.replace("_", " ").title()

        orch = HarnessOrchestrator()
        meta = BookMetadata(
            title=title,
            author=args.author,
            theme=args.theme,
            use_llm_harness=not args.no_llm,
            force_ocr=args.ocr,
        )
        book = orch.process_file(str(in_path), metadata=meta)
        epub_p = build_epub(book, out_dir / f"{in_path.stem}.epub")
        mobi_p = build_mobi(book, out_dir / f"{in_path.stem}.mobi", epub_path=epub_p)
        print(json.dumps({
            "epub": str(epub_p),
            "mobi": str(mobi_p),
            "stats": book.stats.model_dump(),
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
