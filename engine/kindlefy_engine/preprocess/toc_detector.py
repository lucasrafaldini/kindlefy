"""
TOC Detector & Ground-Truth Chapter Segmentation Harness (Pass 0.5)

Identifies Sumário/Índice in the front matter of books (pages 1-25),
extracts canonical chapters and sub-sections, and provides a ground-truth
editorial anchor so Pass 1 and Pass 4 never invent bogus chapters from sub-headings,
broken bold lines, or OCR artifacts.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Optional
from pydantic import BaseModel, Field

from kindlefy_engine.models import (
    BlockRole,
    HarnessAuditEntry,
    HarnessStats,
    RawBlock,
)


class CanonicalTOCItem(BaseModel):
    title: str
    normalized_title: str
    number: Optional[int] = None
    level: int = 1  # 1 = Chapter / Major Section, 2 = Subheading / Inner Section
    page_hint: Optional[int] = None
    matched_block_id: Optional[str] = None


class TOCDetectionResult(BaseModel):
    found: bool = False
    toc_block_ids: set[str] = Field(default_factory=set)
    start_page: int = 0
    end_page: int = 0
    canonical_chapters: list[CanonicalTOCItem] = Field(default_factory=list)
    canonical_sections: list[CanonicalTOCItem] = Field(default_factory=list)


def normalize_text_for_matching(text: str) -> str:
    """Removes accents, punctuation, extra spaces, and lowercases for fuzzy title comparison."""
    if not text:
        return ""
    # NFKD normalization to strip accents
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    stripped = stripped.lower()
    stripped = re.sub(r"[\W_]+", " ", stripped).strip()
    # Remove leading chapter prefixes like 'capitulo 1', 'parte 2', 'cap 1', 'thread 1', 'lettre 1'
    stripped = re.sub(r"^(?:capitulo|chapter|parte|part|thread|email|exhibit|lettre|carta)\s+\w+\b\s*", "", stripped)
    return stripped


def strip_all_spaces(text: str) -> str:
    """Returns normalized text with all whitespace removed for OCR joined-word tolerance."""
    return re.sub(r"\s+", "", normalize_text_for_matching(text))


TOC_START_REGEX = re.compile(
    r"(?:^|\n)\s*(?:sum[áa]rio|índice|indice|table\s+of\s+contents|contents|tabela\s+de\s+conte[úu]do|sommaire|table\s+des\s+mati[èe]res)\b",
    re.IGNORECASE,
)

# Common Roman or Arabic chapter numbering patterns in TOC
CHAPTER_NUM_PREFIX = re.compile(
    r"^(?:(?:cap[íi]tulo|parte|thread|e-?mail|exhibit|lettre|carta)\s+)?([0-9]{1,3}|[ivxlcdm]{1,8}|[1lI]{1,3})[\.\-\s\):]+(.*)$",
    re.IGNORECASE,
)

PAGE_TRAILING_REGEX = re.compile(
    r"[\s\.\-_]+(?:p[áa]g\.?|p\.?)?\s*([0-9]{1,4})\s*$",
    re.IGNORECASE,
)


def detect_and_extract_toc(
    blocks: list[RawBlock],
    stats: HarnessStats,
    audit_log: list[HarnessAuditEntry],
) -> TOCDetectionResult:
    """
    Scans the initial pages of the document to locate the Sumário/Índice,
    tags all blocks on the Sumário page as BlockRole.FRONTMATTER,
    and extracts canonical chapter titles to anchor subsequent chapter segmentation.
    """
    result = TOCDetectionResult()
    if not blocks:
        return result

    # Find the block where the Sumário starts (pages 1 to 25)
    toc_start_idx: Optional[int] = None
    for idx, blk in enumerate(blocks):
        if blk.page_number > 25:
            break
        txt = blk.text.strip()
        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        for l in lines[:5]:
            if TOC_START_REGEX.search(l) and len(l) <= 45:
                toc_start_idx = idx
                result.start_page = blk.page_number
                break
        if toc_start_idx is not None:
            break

    if toc_start_idx is None:
        return result

    result.found = True
    toc_pages = {result.start_page}
    max_doc_page = max((b.page_number for b in blocks), default=result.start_page)

    # Multi-page TOC scanner: check subsequent pages for high density of page references/romans
    for p in range(result.start_page + 1, min(result.start_page + 10, max_doc_page + 1)):
        p_blks = [b for b in blocks if b.page_number == p]
        if not p_blks:
            break
        p_text = " ".join(b.text for b in p_blks)
        page_ref_count = len(re.findall(r"(?:-\s*\d{1,4}\b|\bp\.\s*\d{1,4}\b)", p_text))
        roman_count = len(re.findall(r"\b[IVXLCDM]{1,6}\.\s+[A-Z]", p_text))

        if page_ref_count >= 5 or (roman_count >= 1 and page_ref_count >= 2):
            toc_pages.add(p)
        else:
            # Reached real body reading text
            break

    result.end_page = max(toc_pages)
    toc_blocks: list[RawBlock] = [b for b in blocks if b.page_number in toc_pages]
    for blk in toc_blocks:
        result.toc_block_ids.add(blk.block_id)
        old_role = blk.role
        blk.role = BlockRole.FRONTMATTER
        if old_role != BlockRole.FRONTMATTER:
            audit_log.append(
                HarnessAuditEntry(
                    stage="Pass 0.5: Sumário & TOC Harness",
                    block_id=blk.block_id,
                    page_number=blk.page_number,
                    operation="SET_TOC_FRONTMATTER",
                    before_snippet=blk.text[:70],
                    after_snippet="[FRONTMATTER: Sumário]",
                    source="heuristic",
                    accepted=True,
                    reason="Bloco identificado como parte do Sumário/Índice da obra.",
                )
            )

    # Now parse canonical chapter entries from the raw text inside TOC blocks
    canonical_items: list[CanonicalTOCItem] = []
    canonical_sections: list[CanonicalTOCItem] = []

    all_lines: list[str] = []
    for blk in toc_blocks:
        # Exclude running headers/footers or top/bottom margin edge noise
        if blk.bbox is not None:
            y_top = blk.bbox.y0 / max(1.0, blk.bbox.page_height)
            y_bot = blk.bbox.y1 / max(1.0, blk.bbox.page_height)
            if y_top < 0.050 or y_bot > 0.940:
                continue
        if blk.role in {BlockRole.RUNNING_HEADER, BlockRole.RUNNING_FOOTER, BlockRole.PAGE_NUMBER}:
            continue
        for l in blk.text.split("\n"):
            s = l.strip()
            if not s:
                continue
            if TOC_START_REGEX.search(s) and len(s) <= 30:
                continue
            if re.match(r"^(?:contra[\s\.\-•]+hist[óo]ria|do\s+[li]{1,2}beralismo)\b", s, re.I):
                continue
            # If standalone number, only keep if previous line ended with dash or hyphen (trailing page number)
            if re.match(r"^\d{1,4}$", s):
                if all_lines and all_lines[-1].endswith(("-", "–", "—")):
                    all_lines[-1] = all_lines[-1] + " " + s
                continue
            all_lines.append(s)

    # Check if this book uses Roman numerals for chapters (e.g., I. O que é...)
    has_roman_chapters = any(
        re.match(r"^[IVXLCDM]{1,8}[\.\-\)]\s+", ln) for ln in all_lines
    )

    def is_chapter_start(line_str: str) -> bool:
        if re.search(r"\b(?:p\.|p[áa]g\.)\s*\d+", line_str):
            return False
        if has_roman_chapters:
            if re.match(r"^[0-9]+[\.\)]", line_str):
                return False
            return bool(
                re.match(r"^(?:(?:cap[íi]tulo|parte|thread|e-?mail|exhibit|lettre|carta)\s+)?(?:[ivxlcdm]{1,8})[\.\-\):]\s+[A-ZÀ-Ú\[]", line_str, re.I)
                or re.match(r"^(?:Uma breve premissa|Pref[áa]cio|Introdu[çc][ãa]o|Conclus[ãa]o|Posf[áa]cio|Ep[íi]logo|Refer[êe]ncias|Índice de nomes|Avant-propos|Note éditoriale|Archival Foreword)\b", line_str, re.I)
            )
        else:
            return bool(
                re.match(r"^(?:cap[íi]tulo|chapter|parte|thread|e-?mail|exhibit|lettre|carta)\s+(?:\d+|[ivxlcdm]+)[\.\-\):]+", line_str, re.I)
                or re.match(r"^(?:Pref[áa]cio|Introdu[çc][ãa]o|Conclus[ãa]o|Posf[áa]cio|Ep[íi]logo|Refer[êe]ncias|Índice de nomes|Avant-propos|Note éditoriale|Archival Foreword)\b", line_str, re.I)
            )

    idx = 0
    while idx < len(all_lines):
        line_str = all_lines[idx]
        if is_chapter_start(line_str):
            title_lines = [line_str]
            # Keep gathering lines until we hit the trailing page number (- <digits>)
            while idx + 1 < len(all_lines) and not re.search(r"[\-\–\—]\s*\d+\s*$", " ".join(title_lines)):
                nxt = all_lines[idx + 1]
                if is_chapter_start(nxt) or re.match(r"^[0-9]+[\.\)]", nxt) or re.search(r"\bp\.\s*\d+", nxt):
                    break
                title_lines.append(nxt)
                idx += 1
                if re.search(r"[\-\–\—]\s*\d+\s*$", nxt):
                    break

            full_title = " ".join(title_lines)
            # If line ended with dash and next line is just a number, join it
            if full_title.endswith(("-", "–", "—")) and idx + 1 < len(all_lines):
                nxt = all_lines[idx + 1]
                if re.match(r"^\d{1,4}$", nxt):
                    full_title = full_title + " " + nxt
                    idx += 1

            pm = PAGE_TRAILING_REGEX.search(full_title)
            page_hint = int(pm.group(1)) if pm else None
            clean_title = re.sub(r"[\s\.\-_]+(?:p[áa]g\.?|p\.?)?\s*[0-9]{1,4}\s*$", "", full_title).strip()
            clean_title = re.sub(r"[\s\.\-_]+$", "", clean_title).strip()
            clean_title = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", clean_title)  # de-hyphenate wrapped title words

            # Gather following section lines until next chapter start
            sec_lines = []
            while idx + 1 < len(all_lines):
                nxt = all_lines[idx + 1]
                if is_chapter_start(nxt):
                    break
                sec_lines.append(nxt)
                idx += 1

            # Validate chapter (avoid spurious headers like unpaged 'Introdução')
            if not page_hint and len(clean_title) <= 15 and not sec_lines:
                idx += 1
                continue

            cm = CHAPTER_NUM_PREFIX.match(clean_title)
            num_val = None
            title_part = clean_title
            if cm:
                num_token = cm.group(1)
                title_part = cm.group(2).strip()
                if num_token.isdigit():
                    num_val = int(num_token)
                else:
                    romans = {"i": 1, "ii": 2, "11": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
                    num_val = romans.get(num_token.lower(), None)

            norm = normalize_text_for_matching(title_part)
            if len(norm) >= 3 and not TOC_START_REGEX.search(clean_title):
                canonical_items.append(
                    CanonicalTOCItem(
                        title=clean_title,
                        normalized_title=norm,
                        number=num_val,
                        level=1,
                        page_hint=page_hint,
                    )
                )

            # Parse canonical sections belonging to this chapter
            if sec_lines:
                joined_secs = " ".join(sec_lines)
                joined_secs = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", joined_secs)
                parts = re.split(r"\s*[\-;•]\s*(?=[0-9]+[\.\)])", joined_secs)
                for pt in parts:
                    clean_pt = pt.strip()
                    if not clean_pt:
                        continue
                    m_num = re.match(r"^([0-9]+)[\.\)]\s*", clean_pt)
                    sec_num = int(m_num.group(1)) if m_num else None
                    m_page = re.search(r"\b(?:p\.|p[áa]g\.)\s*([0-9]+)", clean_pt)
                    sec_page = int(m_page.group(1)) if m_page else None
                    sec_title = re.sub(r"\b(?:p\.|p[áa]g\.)\s*[0-9]+", "", clean_pt).strip()
                    sec_title = re.sub(r"^[0-9]+[\.\)]\s*", "", sec_title).strip()
                    sec_title = re.sub(r"[\s,\.\-_]+$", "", sec_title).strip()
                    sec_title = re.sub(r"^[\s,\.\-_]+", "", sec_title).strip()
                    if len(sec_title) >= 4:
                        canonical_sections.append(
                            CanonicalTOCItem(
                                title=sec_title,
                                normalized_title=normalize_text_for_matching(sec_title),
                                number=sec_num,
                                level=2,
                                page_hint=sec_page,
                            )
                        )

        idx += 1

    result.canonical_chapters = canonical_items
    result.canonical_sections = canonical_sections

    if canonical_items:
        stats.editorial_notes.append(
            f"Sumário detectado nas págs {result.start_page}-{result.end_page}: {len(canonical_items)} capítulos e {len(canonical_sections)} seções canônicas identificadas."
        )
        audit_log.append(
            HarnessAuditEntry(
                stage="Pass 0.5: Sumário & TOC Harness",
                block_id=f"p{result.start_page}",
                page_number=result.start_page,
                operation="EXTRACT_CANONICAL_TOC",
                before_snippet=f"{len(toc_blocks)} blocos de sumário",
                after_snippet=f"{len(canonical_items)} capítulos: " + "; ".join(c.title for c in canonical_items[:5]),
                source="heuristic",
                accepted=True,
                reason="TOC Ground-Truth gerado com sucesso para guiar a capitulação.",
            )
        )

    return result


def match_block_to_toc(
    block_text: str,
    toc_result: TOCDetectionResult,
) -> tuple[Optional[CanonicalTOCItem], str]:
    """
    Checks if a block from the book body corresponds to one of the canonical chapters
    or sections extracted from the Sumário.

    Returns (matching_item, 'chapter' | 'section' | 'none').
    """
    if not toc_result.found:
        return None, "none"

    clean_txt = block_text.strip()
    if not clean_txt or len(clean_txt) < 3:
        return None, "none"

    norm_block = normalize_text_for_matching(clean_txt)
    if len(norm_block) < 3:
        return None, "none"

    clean_block_no_spaces = strip_all_spaces(clean_txt)
    words_b = norm_block.split()

    # 1. First test canonical chapters (strict heading qualification)
    is_valid_chapter_candidate = (
        len(clean_txt) <= 130
        and not clean_txt[0].islower()
        and (
            not clean_txt.endswith((".", ",", ";", '"', "”", "'", "’"))
            or re.match(r"^(?:cap[íi]tulo|parte|[ivxlcdm]{1,8}\.)\b", clean_txt, re.I)
        )
    )

    if is_valid_chapter_candidate:
        for item in toc_result.canonical_chapters:
            item_norm = item.normalized_title
            item_no_spaces = strip_all_spaces(item.title)

            # Exact normalized match
            if norm_block == item_norm or clean_block_no_spaces == item_no_spaces:
                return item, "chapter"

            # High sequence similarity
            ratio_norm = difflib.SequenceMatcher(None, item_norm, norm_block).ratio()
            ratio_ns = difflib.SequenceMatcher(None, item_no_spaces, clean_block_no_spaces).ratio()
            if max(ratio_norm, ratio_ns) >= 0.80:
                return item, "chapter"

            # Containment with strict coverage requirement
            if item_norm in norm_block and len(item_norm) >= 0.70 * len(norm_block):
                return item, "chapter"

            if norm_block in item_norm and len(norm_block) >= 0.70 * len(item_norm):
                words_t = item_norm.split()
                if words_b and words_t and words_b[0] == words_t[0]:
                    return item, "chapter"

    # 2. Test canonical sections (sub-items in the Sumário, used to demote to subheading)
    is_valid_section_candidate = (
        len(clean_txt) <= 85
        and not clean_txt[0].islower()
        and not clean_txt.endswith((",", ";", ":", "-", "—", "–"))
        and not bool(re.search(r"\b(?:de|do|da|dos|das|em|no|na|nos|nas|com|sem|por|para|e|ou|que|o|a|os|as)\s*$", clean_txt, re.I))
        and not bool(re.search(r"\b(?:não|ele|ela|eles|elas|mas|porém|contudo|quando|onde|como|porque|definir|iria|reagir)\b", clean_txt, re.I))
    )

    if not is_valid_section_candidate:
        return None, "none"

    for sec in toc_result.canonical_sections:
        sec_norm = sec.normalized_title
        sec_no_spaces = strip_all_spaces(sec.title)

        if norm_block == sec_norm or clean_block_no_spaces == sec_no_spaces:
            return sec, "section"

        ratio = difflib.SequenceMatcher(None, sec_norm, norm_block).ratio()
        if ratio >= 0.85:
            return sec, "section"

        if sec_norm in norm_block and len(sec_norm) >= 0.80 * len(norm_block):
            return sec, "section"
        if norm_block in sec_norm and len(norm_block) >= 0.80 * len(sec_norm):
            return sec, "section"

    return None, "none"
