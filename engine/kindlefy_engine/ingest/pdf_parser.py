from __future__ import annotations

from pathlib import Path
from typing import Tuple
import pymupdf as fitz

from kindlefy_engine.ingest.ocr_extractor import ocr_image_bytes
from kindlefy_engine.models import AmbiguityFlag, BoundingBox, RawBlock


def _detect_two_column_gutter(
    lines: list[dict], page_width: float, page_height: float
) -> float | None:
    """
    XY-Cut Vertical Valley Analysis:
    Checks if the middle third of the page has a vertical whitespace gutter
    separating left and right column blocks.
    Returns the x-coordinate of the gutter if the page is multi-column, else None.
    """
    body_lines = [
        ln
        for ln in lines
        if page_height * 0.10 < ln["y0"] < page_height * 0.90
        and (ln["x1"] - ln["x0"]) < page_width * 0.48
    ]
    if len(body_lines) < 6:
        return None

    mid_x = page_width / 2.0
    gutter_min = page_width * 0.38
    gutter_max = page_width * 0.62

    left_count = 0
    right_count = 0
    crossing_count = 0

    for ln in body_lines:
        if ln["x1"] <= mid_x + 12:
            left_count += 1
        elif ln["x0"] >= mid_x - 12:
            right_count += 1
        elif ln["x0"] < gutter_min and ln["x1"] > gutter_max:
            crossing_count += 1

    if left_count >= 3 and right_count >= 3 and crossing_count <= max(1, len(body_lines) // 10):
        return mid_x
    return None


def parse_pdf_spatially(
    pdf_path: str | Path, force_ocr: bool = False
) -> Tuple[list[RawBlock], int, int, int]:
    """
    Extracts lines/blocks from a PDF with 2D spatial layout preservation,
    font-size & style tracking, and XY-cut multi-column reading order reconstruction.
    Automatically detects scanned/image-only pages and executes RapidOCR ONNX.
    Returns (blocks, total_pages, multi_column_pages_count, scanned_pages_ocr_count).
    """
    doc = fitz.open(str(pdf_path))
    raw_blocks: list[RawBlock] = []
    multi_column_pages = 0
    scanned_pages_ocr_count = 0
    block_counter = 1

    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1
        rect = page.rect
        page_w = float(rect.width) if rect.width > 0 else 595.0
        page_h = float(rect.height) if rect.height > 0 else 842.0

        page_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
        extracted_lines: list[dict] = []

        if not force_ocr:
            for b in page_dict.get("blocks", []):
                if b.get("type") != 0:
                    continue
                for line in b.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    line_text_parts: list[str] = []
                    max_size = 0.0
                    font_name = "Serif"
                    bold_votes = 0
                    italic_votes = 0
                    total_chars = 0

                    for sp in spans:
                        t = sp.get("text", "")
                        if not t:
                            continue
                        line_text_parts.append(t)
                        sz = float(sp.get("size", 11.0))
                        if sz > max_size:
                            max_size = sz
                            font_name = sp.get("font", "Serif")
                        flags = int(sp.get("flags", 0))
                        fn_lower = sp.get("font", "").lower()
                        char_len = len(t.strip())
                        total_chars += char_len
                        if (flags & 16) or "bold" in fn_lower or "black" in fn_lower or "heavy" in fn_lower:
                            bold_votes += char_len
                        if (flags & 2) or "italic" in fn_lower or "oblique" in fn_lower:
                            italic_votes += char_len

                    joined = "".join(line_text_parts).strip()
                    if not joined:
                        continue

                    bbox = line.get("bbox", (0.0, 0.0, 0.0, 0.0))
                    extracted_lines.append(
                        {
                            "text": joined,
                            "x0": float(bbox[0]),
                            "y0": float(bbox[1]),
                            "x1": float(bbox[2]),
                            "y1": float(bbox[3]),
                            "font_size": round(max_size or 11.0, 2),
                            "font_name": font_name,
                            "is_bold": bold_votes > (total_chars * 0.5) if total_chars > 0 else False,
                            "is_italic": italic_votes > (total_chars * 0.5) if total_chars > 0 else False,
                            "is_ocr": False,
                        }
                    )

        total_extracted_chars = sum(len(ln["text"]) for ln in extracted_lines)

        # Scanned page fallback: if no text found or characters count < 35 on the page
        if force_ocr or total_extracted_chars < 35:
            pix = page.get_pixmap(dpi=200)
            ocr_lines = ocr_image_bytes(pix.tobytes("png"), page_w, page_h)
            if ocr_lines:
                extracted_lines = ocr_lines
                scanned_pages_ocr_count += 1

        if not extracted_lines:
            continue

        gutter_x = _detect_two_column_gutter(extracted_lines, page_w, page_h)
        if gutter_x is not None:
            multi_column_pages += 1
            # Partition into top full-width, left column, right column, bottom full-width
            top_spanning = []
            col_left = []
            col_right = []
            bottom_spanning = []

            for ln in extracted_lines:
                width = ln["x1"] - ln["x0"]
                if width > page_w * 0.52 or ln["y0"] <= page_h * 0.09:
                    if ln["y0"] < page_h * 0.5:
                        top_spanning.append((0, ln))
                    else:
                        bottom_spanning.append((3, ln))
                elif ln["x0"] < gutter_x - 10:
                    col_left.append((1, ln))
                else:
                    col_right.append((2, ln))

            top_spanning.sort(key=lambda item: (round(item[1]["y0"], 1), item[1]["x0"]))
            col_left.sort(key=lambda item: (round(item[1]["y0"], 1), item[1]["x0"]))
            col_right.sort(key=lambda item: (round(item[1]["y0"], 1), item[1]["x0"]))
            bottom_spanning.sort(key=lambda item: (round(item[1]["y0"], 1), item[1]["x0"]))

            ordered_lines = top_spanning + col_left + col_right + bottom_spanning
        else:
            extracted_lines.sort(key=lambda ln: (round(ln["y0"], 1), ln["x0"]))
            ordered_lines = [(0, ln) for ln in extracted_lines]

        # Compute left margin baseline per column
        col_min_x: dict[int, float] = {}
        for col_idx, ln in ordered_lines:
            if col_idx not in col_min_x or ln["x0"] < col_min_x[col_idx]:
                col_min_x[col_idx] = ln["x0"]

        prev_y1_by_col: dict[int, float] = {}
        for col_idx, ln in ordered_lines:
            base_x = col_min_x.get(col_idx, 0.0)
            indent = max(0.0, round(ln["x0"] - base_x, 1))
            prev_y1 = prev_y1_by_col.get(col_idx)
            space_before = max(0.0, round(ln["y0"] - prev_y1, 1)) if prev_y1 is not None else 0.0
            prev_y1_by_col[col_idx] = ln["y1"]

            alpha_chars = [c for c in ln["text"] if c.isalpha()]
            is_caps = len(alpha_chars) >= 3 and all(c.isupper() for c in alpha_chars)
            is_ocr = ln.get("is_ocr", False)
            flags: list[AmbiguityFlag] = [AmbiguityFlag.OCR_ARTIFACT_SPAN] if is_ocr else []

            raw_blocks.append(
                RawBlock(
                    block_id=f"B{block_counter:05d}",
                    page_number=page_num,
                    column_index=col_idx,
                    text=ln["text"],
                    original_text=ln["text"],
                    font_size=ln["font_size"],
                    font_name=ln["font_name"],
                    is_bold=ln["is_bold"],
                    is_italic=ln["is_italic"],
                    is_all_caps=is_caps,
                    indent_left=indent,
                    space_before=space_before,
                    confidence=ln.get("confidence", 1.0),
                    ambiguity_flags=flags,
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
            block_counter += 1

    total_pages = len(doc)
    doc.close()
    return raw_blocks, total_pages, multi_column_pages, scanned_pages_ocr_count
