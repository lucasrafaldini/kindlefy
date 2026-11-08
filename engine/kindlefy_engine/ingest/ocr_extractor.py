from __future__ import annotations

import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from typing import Any, Optional, Tuple
import numpy as np
from PIL import Image

try:
    from rapidocr_onnxruntime import RapidOCR
    _OCR_ENGINE: Optional[RapidOCR] = None

    def get_ocr_engine() -> RapidOCR:
        global _OCR_ENGINE
        if _OCR_ENGINE is None:
            _OCR_ENGINE = RapidOCR()
        return _OCR_ENGINE

except ImportError:
    get_ocr_engine = None  # type: ignore


VISION_BIN_PATH = Path(__file__).parent / "vision_ocr_bin"


def _run_apple_vision_ocr(
    img_bytes: bytes, target_width: float, target_height: float
) -> list[dict[str, Any]]:
    """
    Executes native Apple Vision OCR on macOS via vision_ocr_bin.
    Delivers outstanding accuracy for Portuguese (accents ã, ç, é), correct spacing,
    and punctation, hardware accelerated by Apple Neural Engine & Metal.
    """
    if not (platform.system().lower() == "darwin" and VISION_BIN_PATH.exists()):
        return []

    # Write temp file for vision_ocr_bin
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(img_bytes)
        tmp_path = Path(tmp.name)

    try:
        out = subprocess.check_output([str(VISION_BIN_PATH), str(tmp_path)], timeout=15)
        raw_items = json.loads(out.decode("utf-8"))
        if not raw_items:
            return []

        # Get image dimensions to compute scaling to target_width x target_height
        pil_img = Image.open(tmp_path)
        img_w, img_h = pil_img.size

        scale_x = target_width / max(1.0, float(img_w))
        scale_y = target_height / max(1.0, float(img_h))

        extracted: list[dict[str, Any]] = []
        for it in raw_items:
            text = it.get("text", "").strip()
            if not text:
                continue

            # Fix glued words if any (e.g. "doAtlantico" -> "do Atlantico")
            text = re.sub(r"\b(do|da|de|em|no|na|com|por|para|e|o|a)([A-ZÀ-ÖØ-Þ])", r"\1 \2", text)
            text = re.sub(r"([a-zà-öø-ÿ])([A-ZÀ-ÖØ-Þ])", r"\1 \2", text)

            x0 = it.get("x0", 0.0) * scale_x
            y0 = it.get("y0", 0.0) * scale_y
            x1 = it.get("x1", 0.0) * scale_x
            y1 = it.get("y1", 0.0) * scale_y
            box_h = max(6.0, y1 - y0)
            font_sz = round(max(8.0, min(36.0, box_h * 0.78)), 1)

            extracted.append(
                {
                    "text": text,
                    "x0": round(x0, 1),
                    "y0": round(y0, 1),
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "font_size": font_sz,
                    "font_name": "Vision-Serif",
                    "is_bold": False,
                    "is_italic": False,
                    "confidence": it.get("confidence", 0.98),
                    "is_ocr": True,
                }
            )
        return extracted
    except Exception as e:
        return []
    finally:
        tmp_path.unlink(missing_ok=True)


def ocr_image_bytes(
    img_bytes: bytes, target_width: float, target_height: float
) -> list[dict[str, Any]]:
    """
    Universal OCR router:
    1. On macOS: Uses native Apple Vision OCR (fast, perfect Portuguese accents & word separation).
    2. Fallback: RapidOCR ONNX (cross-platform for Windows/Linux).
    """
    # 1. Try Apple Vision first if on macOS
    if platform.system().lower() == "darwin" and VISION_BIN_PATH.exists():
        vision_res = _run_apple_vision_ocr(img_bytes, target_width, target_height)
        if vision_res:
            return vision_res

    # 2. RapidOCR ONNX fallback
    if get_ocr_engine is None:
        return []

    ocr = get_ocr_engine()
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    px_w, px_h = pil_img.size
    np_img = np.array(pil_img)

    result, _elapse = ocr(np_img)
    if not result:
        return []

    scale_x = target_width / max(1.0, float(px_w))
    scale_y = target_height / max(1.0, float(px_h))

    extracted_lines: list[dict[str, Any]] = []

    for item in result:
        box, text, score = item[0], item[1], float(item[2])
        stripped = text.strip()
        if not stripped or score < 0.35:
            continue

        # Separate glued words common in OCR
        stripped = re.sub(r"([a-zà-öø-ÿ])([A-ZÀ-ÖØ-Þ])", r"\1 \2", stripped)
        stripped = re.sub(r"\b(do|da|de|em|no|na|com|por|para|e|o|a)([A-ZÀ-ÖØ-Þ])", r"\1 \2", stripped)

        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        x0_pt = min(xs) * scale_x
        y0_pt = min(ys) * scale_y
        x1_pt = max(xs) * scale_x
        y1_pt = max(ys) * scale_y

        box_h = max(6.0, y1_pt - y0_pt)
        estimated_font_size = round(max(8.0, min(36.0, box_h * 0.78)), 1)

        extracted_lines.append(
            {
                "text": stripped,
                "x0": round(x0_pt, 1),
                "y0": round(y0_pt, 1),
                "x1": round(x1_pt, 1),
                "y1": round(y1_pt, 1),
                "font_size": estimated_font_size,
                "font_name": "OCR-Serif",
                "is_bold": False,
                "is_italic": False,
                "confidence": score,
                "is_ocr": True,
            }
        )

    return extracted_lines
