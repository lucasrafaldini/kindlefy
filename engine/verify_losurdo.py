from __future__ import annotations

from pathlib import Path
import fitz
from kindlefy_engine.harness.orchestrator import HarnessOrchestrator
from kindlefy_engine.models import BookMetadata

LOSURDO_PDF = "/Users/outis/Downloads/Domenico Losurdo - Contra-História do Liberalismo-Editora Idéias e Letras (2006).pdf"

def main():
    pdf_path = Path(LOSURDO_PDF)
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return

    # Extract first 10 pages to a test pdf in /tmp
    doc = fitz.open(str(pdf_path))
    sample_doc = fitz.open()
    for i in range(min(10, len(doc))):
        sample_doc.insert_pdf(doc, from_page=i, to_page=i)
    
    out_sample = Path("/tmp/losurdo_sample_10p.pdf")
    sample_doc.save(str(out_sample))
    sample_doc.close()
    doc.close()
    print(f"Sample PDF created at {out_sample} (pages 1-10)")

    orch = HarnessOrchestrator()
    meta = BookMetadata(
        title="Contra-História do Liberalismo",
        author="Domenico Losurdo",
        language="pt-BR",
        theme="classic",
        enable_drop_caps=True,
    )

    print("Processing sample with HarnessOrchestrator...")
    book = orch.process_file(str(out_sample), metadata=meta)

    print(f"\n--- SUCCESS: Processed {book.stats.total_pages_parsed} pages ---")
    print(f"Chapters found: {len(book.chapters)}")
    for i, ch in enumerate(book.chapters):
        print(f"  [{i}] ID={ch.chapter_id} | Title='{ch.title}' | Role={ch.role} | Blocks={len(ch.blocks)}")
        if ch.blocks:
            first_block = ch.blocks[0]
            print(f"       First block: {first_block.text[:80]}...")

    # Now let's compile EPUB to see the HTML formatting
    from kindlefy_engine.compiler.epub_builder import build_epub
    epub_out = Path("/tmp/losurdo_sample.epub")
    epub_path = build_epub(book, epub_out)
    print(f"\nEPUB built successfully at {epub_path} ({epub_path.stat().st_size:,} bytes)")

if __name__ == "__main__":
    main()
