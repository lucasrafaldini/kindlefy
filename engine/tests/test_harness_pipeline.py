from __future__ import annotations

from pathlib import Path
import zipfile
from kindlefy_engine.compiler.epub_builder import build_epub, validate_epub_archive
from kindlefy_engine.compiler.mobi_builder import build_mobi
from kindlefy_engine.demo_samples import create_torture_test_pdf
from kindlefy_engine.harness.invariant_guard import InvariantGuard
from kindlefy_engine.harness.orchestrator import HarnessOrchestrator
from kindlefy_engine.models import BlockRole, BookMetadata, HarnessAuditEntry, RawBlock


def test_torture_pdf_full_pipeline(tmp_path: Path) -> None:
    pdf_path = create_torture_test_pdf(tmp_path / "torture.pdf")
    assert pdf_path.exists()

    orch = HarnessOrchestrator()
    meta = BookMetadata(
        title="Crônicas do Horizonte Perdido",
        author="Mestre Tipógrafo",
        language="pt-BR",
        theme="classic",
    )
    book = orch.process_file(str(pdf_path), metadata=meta)

    # 1. Verify multi-column XY-Cut reflow detected Page 2's 2-column layout
    assert book.stats.total_pages_parsed == 2
    assert book.stats.multi_column_pages_reflowed == 1

    # 2. Verify running headers and page numbers (- 1 -, - 2 -) were stripped
    assert book.stats.running_headers_stripped >= 3
    all_text = "\n".join(b.text for ch in book.chapters for b in ch.blocks)
    assert "EDIÇÃO DE PROVA" not in all_text
    assert "- 1 -" not in all_text

    # 3. Verify chapters & subtitles were paired properly
    assert len(book.chapters) == 2
    assert book.chapters[0].title == "Capítulo 1"
    assert book.chapters[0].subtitle == "O Labirinto de Papel"
    assert book.chapters[1].title == "Capítulo 2"
    assert book.chapters[1].subtitle == "As Duas Colunas do Tempo"

    # 4. Verify syllable de-hyphenation vs compound hyphen preservation
    assert "desenvolvimento silencioso" in all_text
    assert "guarda-chuva escuro" in all_text

    # 5. Verify OCR Micro-Span Surgeon repaired 'c0nhecimen1o' and 'pensamen1o'
    # while InvariantGuard protected 'MP3'
    assert "conhecimento acumulado" in all_text
    assert "pensamento raro" in all_text
    assert "MP3 antigo" in all_text

    # 6. Verify page-crossing sentence stitch between Page 1 bottom and Page 2 top
    assert "onde termina o silêncio entre um capítulo e outro" in all_text

    # 7. Verify 2-column reading order on Page 2 (left column completely before right column)
    left_pos = all_text.find("impressos em duas colunas estreitas")
    right_pos = all_text.find("espaço em branco no centro da folha")
    assert left_pos != -1 and right_pos != -1
    assert left_pos < right_pos

    # 8. Verify EPUB 3 compilation & strict validation
    epub_path = build_epub(book, tmp_path / "out.epub")
    val = validate_epub_archive(epub_path)
    assert val["valid"] is True
    with zipfile.ZipFile(str(epub_path), "r") as zf:
        assert zf.infolist()[0].filename == "mimetype"
        assert zf.infolist()[0].compress_type == zipfile.ZIP_STORED

    # 9. Verify MOBI binary compilation (PalmDOC + MOBI + EXTH magic bytes)
    mobi_path = build_mobi(book, tmp_path / "out.mobi")
    mobi_bytes = mobi_path.read_bytes()
    assert b"BOOKMOBI" in mobi_bytes[:80]
    assert b"EXTH" in mobi_bytes
    assert "Crônicas do Horizonte Perdido".encode("utf-8") in mobi_bytes


def test_invariant_guard_blocks_hallucinations() -> None:
    blk = RawBlock(
        block_id="B0001",
        page_number=1,
        text="O formato MP3 revolucionou a música digital na década de noventa.",
        role=BlockRole.PARAGRAPH,
    )
    audit: list[HarnessAuditEntry] = []

    # Should block mutating protected technical token 'MP3'
    ok1, _ = InvariantGuard.verify_ocr_patch(blk, "MP3", "MPB", audit)
    assert not ok1

    # Should block replacing a word with an unrelated hallucinated phrase
    ok2, _ = InvariantGuard.verify_ocr_patch(
        blk, "música", "arquitetura gótica medieval inteira", audit
    )
    assert not ok2

    # Should block stripping a full narrative paragraph as a running_header
    ok3, role3 = InvariantGuard.verify_role_classification(
        blk, BlockRole.RUNNING_HEADER, audit
    )
    assert not ok3
    assert role3 == BlockRole.PARAGRAPH


def test_scanned_image_ocr_pipeline(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (900, 500), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((80, 60), "Capitulo 1", fill=(0, 0, 0))
    draw.text((80, 100), "A Descoberta do Arquivo Secreto", fill=(0, 0, 0))
    draw.text((80, 150), "Este e um documento escaneado processado via OCR neural com alta fidelidade.", fill=(0, 0, 0))
    img_path = tmp_path / "pagina_escaneada.png"
    img.save(img_path)

    orch = HarnessOrchestrator()
    book = orch.process_file(str(img_path))
    assert book.stats.scanned_pages_ocr_processed == 1
    assert len(book.chapters) >= 1
    all_text = " ".join(b.text for ch in book.chapters for b in ch.blocks)
    assert any(term in all_text for term in ["Capitulo", "Descoberta", "documento", "escaneado", "fidelidade"])
