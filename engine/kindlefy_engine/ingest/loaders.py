from __future__ import annotations

from pathlib import Path
from typing import Tuple
import zipfile
import chardet
from bs4 import BeautifulSoup
import docx
from PIL import Image

from kindlefy_engine.ingest.ocr_extractor import ocr_image_bytes
from kindlefy_engine.ingest.pdf_parser import parse_pdf_spatially
from kindlefy_engine.models import AmbiguityFlag, BlockRole, BoundingBox, RawBlock


def _read_text_with_charset(path: Path) -> str:
    raw_bytes = path.read_bytes()
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        detected = chardet.detect(raw_bytes)
        encoding = detected.get("encoding") or "latin-1"
        return raw_bytes.decode(encoding, errors="replace")


def _parse_plain_or_markdown(path: Path) -> Tuple[list[RawBlock], int, int]:
    content = _read_text_with_charset(path)
    lines = content.splitlines()
    blocks: list[RawBlock] = []
    block_counter = 1
    page_estimate = max(1, len(lines) // 38)

    empty_streak = 0
    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped:
            empty_streak += 1
            continue

        page_num = (idx // 38) + 1
        font_size = 11.0
        is_bold = False
        is_italic = False
        role = BlockRole.PARAGRAPH

        # Markdown syntax hints
        if stripped.startswith("# "):
            stripped = stripped[2:].strip()
            font_size = 18.0
            is_bold = True
            role = BlockRole.CHAPTER_TITLE
        elif stripped.startswith("## "):
            stripped = stripped[3:].strip()
            font_size = 14.5
            is_bold = True
            role = BlockRole.SUBHEADING
        elif stripped.startswith("### "):
            stripped = stripped[4:].strip()
            font_size = 13.0
            is_bold = True
            role = BlockRole.SUBHEADING
        elif stripped.startswith("> "):
            stripped = stripped[2:].strip()
            is_italic = True
            role = BlockRole.BLOCKQUOTE
        elif stripped in {"***", "* * *", "---", "- - -", "___"}:
            role = BlockRole.SCENE_BREAK

        alpha_chars = [c for c in stripped if c.isalpha()]
        is_caps = len(alpha_chars) >= 3 and all(c.isupper() for c in alpha_chars)
        indent = float(len(raw_line) - len(raw_line.lstrip(" \t"))) * 4.0

        blocks.append(
            RawBlock(
                block_id=f"B{block_counter:05d}",
                page_number=page_num,
                text=stripped,
                original_text=stripped,
                font_size=font_size,
                is_bold=is_bold,
                is_italic=is_italic,
                is_all_caps=is_caps,
                indent_left=indent,
                space_before=14.0 if empty_streak > 0 else 2.0,
                role=role,
            )
        )
        block_counter += 1
        empty_streak = 0

    return blocks, page_estimate, 0


def _parse_docx(path: Path) -> Tuple[list[RawBlock], int, int]:
    document = docx.Document(str(path))
    blocks: list[RawBlock] = []
    block_counter = 1

    for idx, para in enumerate(document.paragraphs):
        text = para.text.strip()
        if not text:
            continue

        style_name = (para.style.name if para.style else "").lower()
        font_size = 11.0
        is_bold = False
        is_italic = False
        role = BlockRole.PARAGRAPH

        if "heading 1" in style_name or "title" in style_name:
            font_size = 18.0
            is_bold = True
            role = BlockRole.CHAPTER_TITLE
        elif "heading 2" in style_name or "heading 3" in style_name or "subtitle" in style_name:
            font_size = 14.0
            is_bold = True
            role = BlockRole.SUBHEADING
        elif "quote" in style_name:
            is_italic = True
            role = BlockRole.BLOCKQUOTE

        # Also inspect run-level formatting
        if para.runs:
            bold_chars = sum(len(r.text) for r in para.runs if r.bold)
            italic_chars = sum(len(r.text) for r in para.runs if r.italic)
            if bold_chars > len(text) * 0.6:
                is_bold = True
            if italic_chars > len(text) * 0.6:
                is_italic = True

        alpha_chars = [c for c in text if c.isalpha()]
        is_caps = len(alpha_chars) >= 3 and all(c.isupper() for c in alpha_chars)

        blocks.append(
            RawBlock(
                block_id=f"B{block_counter:05d}",
                page_number=(idx // 25) + 1,
                text=text,
                original_text=text,
                font_size=font_size,
                is_bold=is_bold,
                is_italic=is_italic,
                is_all_caps=is_caps,
                space_before=12.0,
                role=role,
            )
        )
        block_counter += 1

    return blocks, max(1, len(blocks) // 25), 0


def _parse_html_content(html_str: str, start_counter: int = 1, page_num: int = 1) -> list[RawBlock]:
    soup = BeautifulSoup(html_str, "lxml")
    for tag in soup(["script", "style", "head", "nav"]):
        tag.decompose()

    blocks: list[RawBlock] = []
    counter = start_counter
    elements = soup.find_all(["h1", "h2", "h3", "h4", "p", "blockquote", "hr", "li", "div"])

    for el in elements:
        if el.name == "div" and el.find(["p", "h1", "h2", "h3", "blockquote"]):
            continue
        if el.name == "hr":
            blocks.append(
                RawBlock(
                    block_id=f"B{counter:05d}",
                    page_number=page_num,
                    text="* * *",
                    original_text="* * *",
                    role=BlockRole.SCENE_BREAK,
                )
            )
            counter += 1
            continue

        text = " ".join(el.get_text(" ", strip=True).split())
        if not text:
            continue

        font_size = 11.0
        is_bold = False
        is_italic = False
        role = BlockRole.PARAGRAPH

        if el.name == "h1":
            font_size = 18.0
            is_bold = True
            role = BlockRole.CHAPTER_TITLE
        elif el.name in {"h2", "h3", "h4"}:
            font_size = 14.0
            is_bold = True
            role = BlockRole.SUBHEADING
        elif el.name == "blockquote":
            is_italic = True
            role = BlockRole.BLOCKQUOTE

        alpha_chars = [c for c in text if c.isalpha()]
        is_caps = len(alpha_chars) >= 3 and all(c.isupper() for c in alpha_chars)

        blocks.append(
            RawBlock(
                block_id=f"B{counter:05d}",
                page_number=page_num,
                text=text,
                original_text=text,
                font_size=font_size,
                is_bold=is_bold,
                is_italic=is_italic,
                is_all_caps=is_caps,
                space_before=12.0,
                role=role,
            )
        )
        counter += 1

    return blocks


def _parse_epub(path: Path) -> Tuple[list[RawBlock], int, int]:
    blocks: list[RawBlock] = []
    counter = 1
    page_num = 1
    with zipfile.ZipFile(str(path), "r") as zf:
        html_files = [
            name
            for name in zf.namelist()
            if name.lower().endswith((".xhtml", ".html", ".htm"))
            and "nav" not in name.lower()
            and "toc" not in name.lower()
        ]
        for fname in sorted(html_files):
            raw = zf.read(fname)
            detected = chardet.detect(raw)
            enc = detected.get("encoding") or "utf-8"
            html_str = raw.decode(enc, errors="replace")
            doc_blocks = _parse_html_content(html_str, start_counter=counter, page_num=page_num)
            blocks.extend(doc_blocks)
            counter += len(doc_blocks)
            page_num += 1

    return blocks, max(1, page_num - 1), 0


def _parse_scanned_image(path: Path) -> Tuple[list[RawBlock], int, int, int]:
    """Runs RapidOCR on a standalone image file (scanned book page, photo)."""
    raw_bytes = path.read_bytes()
    pil_img = Image.open(path)
    img_w, img_h = pil_img.size
    page_w = 595.0
    page_h = round((img_h / max(1.0, img_w)) * page_w, 1)

    ocr_lines = ocr_image_bytes(raw_bytes, page_w, page_h)
    blocks: list[RawBlock] = []

    ocr_lines.sort(key=lambda ln: (round(ln["y0"], 1), ln["x0"]))

    for idx, ln in enumerate(ocr_lines, start=1):
        alpha_chars = [c for c in ln["text"] if c.isalpha()]
        is_caps = len(alpha_chars) >= 3 and all(c.isupper() for c in alpha_chars)

        blocks.append(
            RawBlock(
                block_id=f"B{idx:05d}",
                page_number=1,
                text=ln["text"],
                original_text=ln["text"],
                font_size=ln["font_size"],
                is_all_caps=is_caps,
                confidence=ln.get("confidence", 0.9),
                ambiguity_flags=[AmbiguityFlag.OCR_ARTIFACT_SPAN],
                bbox=BoundingBox(
                    x0=ln["x0"],
                    y0=ln["y0"],
                    x1=ln["x1"],
                    y1=ln["y1"],
                    page_width=page_w,
                    page_height=page_h,
                ),
            )
        )
    return blocks, 1, 0, 1


def ingest_document(
    file_path: str | Path, force_ocr: bool = False
) -> Tuple[list[RawBlock], int, int, int]:
    """
    Universal document ingestion router for:
    - PDF (native text and auto-detected scanned pages / force_ocr)
    - Standalone scanned images (.png, .jpg, .jpeg, .webp, .tiff)
    - Text manuscripts (.txt, .md, .markdown)
    - Word documents (.docx)
    - HTML and malformed EPUBs
    Returns (raw_blocks, total_pages, multi_column_pages, scanned_pages_ocr_count).
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        return _parse_scanned_image(path)
    if suffix == ".pdf":
        return parse_pdf_spatially(path, force_ocr=force_ocr)
    if suffix in {".txt", ".md", ".markdown"}:
        b, p, mc = _parse_plain_or_markdown(path)
        return b, p, mc, 0
    if suffix == ".docx":
        b, p, mc = _parse_docx(path)
        return b, p, mc, 0
    if suffix in {".html", ".htm", ".xhtml"}:
        html_str = _read_text_with_charset(path)
        blocks = _parse_html_content(html_str)
        return blocks, max(1, len(blocks) // 25), 0, 0
    if suffix == ".epub":
        b, p, mc = _parse_epub(path)
        return b, p, mc, 0

    # Default fallback as plain text
    b, p, mc = _parse_plain_or_markdown(path)
    return b, p, mc, 0
