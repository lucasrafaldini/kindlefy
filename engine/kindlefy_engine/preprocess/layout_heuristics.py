from __future__ import annotations

from collections import Counter
import re
from typing import Tuple

from kindlefy_engine.models import (
    AmbiguityFlag,
    BlockRole,
    HarnessAuditEntry,
    HarnessStats,
    RawBlock,
)
from kindlefy_engine.preprocess.lexical_cleaner import clean_block_lexically

CHAPTER_REGEX = re.compile(
    r"^(?:cap[íi]tulo|chapter|cap\.?|thread|e-?mail|exhibit|lettre|carta)\s+(?:\d+|[ivxlcdm]+|um|dois|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez|un|deux|trois|quatre|cinq)\b",
    re.IGNORECASE,
)
PART_REGEX = re.compile(
    r"^(?:parte|part|livro|book|dossier|volume)\s+(?:\d+|[ivxlcdm]+|um|dois|tr[êe]s|quatro|primeira|segunda|terceira)\b",
    re.IGNORECASE,
)
SPECIAL_SECTION_REGEX = re.compile(
    r"^(?:pr[óo]logo|ep[íi]logo|pref[áa]cio|introdu[çc][ãa]o|conclus[ãa]o|posf[áa]cio|agradecimentos|notas|sum[áa]rio|ap[êe]ndice|uma\s+breve\s+premissa\s+metodol[óo]gica|avant-propos|notice\s+biographique|note\s+éditoriale|archival\s+foreword)\s*$",
    re.IGNORECASE,
)
EMAIL_HEADER_REGEX = re.compile(
    r"^(?:From|To|Cc|Bcc|Date|Sent|Subject|Bates|De|Para|Data|Assunto|Expéditeur|Destinataire|Objet)\s*:\s*.+",
    re.IGNORECASE,
)
EMAIL_DIVIDER_REGEX = re.compile(
    r"^(?:-{3,}\s*Forwarded\s+message\s*-{3,}|-{3,}\s*Original\s+Message\s*-{3,}|On\s+.+wrote\s*:|>+\s+)",
    re.IGNORECASE,
)
FRONTMATTER_MARKERS_REGEX = re.compile(
    r"(?:ficha\s+catalogr[áa]fica|diretores\s+editoriais|coordena[çc][ãa]o\s+editorial|"
    r"todos\s+os\s+direitos|isbn\s*[\d\-]+|copyright|edi[çc][ãa]o\s+brasileira|"
    r"tradu[çc][ãa]o\s+de|t[íi]tulo\s+original|cdd-[\d\.]+|dados\s+internacionais|"
    r"editora\s+ideias|editora\s+id[ée]ias|\b\d+\s*ª?\s*edi[çc][ãa]o\b)",
    re.IGNORECASE,
)
PAGE_NUM_REGEX = re.compile(
    r"^(?:[-–—\s]*\d{1,4}[-–—\s]*|p[áa]g(?:ina)?\.?\s*\d{1,4}(?:\s*de\s*\d{1,4})?|[ivxlcdm]{1,6})$",
    re.IGNORECASE,
)
SCENE_BREAK_REGEX = re.compile(r"^(?:\*\s*\*\s*\*|\*{3,}|-{3,}|—{3,}|~{3,}|•\s*•\s*•)$")
TERMINAL_PUNCTUATION = (".", "!", "?", "…", ":", ";", "”", '"', "’", "'", ")", "]")


def _normalize_header_fingerprint(text: str) -> str:
    # Replace digits with '#' to group "Book Title - 12" and "Book Title - 13"
    lowered = re.sub(r"\d+", "#", text.strip().lower())
    return re.sub(r"\s+", " ", lowered)


def run_spatial_and_structural_heuristics(
    blocks: list[RawBlock],
    stats: HarnessStats,
    audit_log: list[HarnessAuditEntry],
) -> Tuple[list[RawBlock], float]:
    """
    Pass 0:
    1. Cleans lexical/encoding/ligature issues in all blocks.
    2. Computes body font-size mode across the document.
    3. Identifies and marks repeating running headers, footers, and standalone page numbers.
    4. Detects candidate headings (Part, Chapter, Subheading) and scene breaks.
    5. Flags ambiguous paragraph breaks and heading boundaries for Gemma 2 2B review.
    Returns (processed_blocks, body_font_size).
    """
    if not blocks:
        return [], 11.0

    # 1. Lexical cleaning
    for idx, blk in enumerate(blocks):
        blocks[idx] = clean_block_lexically(blk, audit_log)

    # 2. Compute modal body font size weighted by character count
    size_weights: Counter[float] = Counter()
    for blk in blocks:
        rounded_sz = round(blk.font_size * 2) / 2.0
        size_weights[rounded_sz] += len(blk.text)
    body_font_size = size_weights.most_common(1)[0][0] if size_weights else 11.0

    # 3. Detect repeating headers/footers across pages
    edge_fingerprints: Counter[str] = Counter()
    for blk in blocks:
        if len(blk.text) <= 75:
            is_near_edge = False
            if blk.bbox:
                y_rel_top = blk.bbox.y0 / max(1.0, blk.bbox.page_height)
                y_rel_bot = blk.bbox.y1 / max(1.0, blk.bbox.page_height)
                if y_rel_top <= 0.11 or y_rel_bot >= 0.89:
                    is_near_edge = True
            if is_near_edge or PAGE_NUM_REGEX.match(blk.text):
                fp = _normalize_header_fingerprint(blk.text)
                if fp:
                    edge_fingerprints[fp] += 1

    seen_first_chapter = False

    for blk in blocks:
        txt = blk.text.strip()
        if not txt:
            continue

        # Scene break check
        if SCENE_BREAK_REGEX.match(txt):
            blk.role = BlockRole.SCENE_BREAK
            continue

        # Standalone page number check
        is_edge = False
        is_top_edge = False
        is_bottom_edge = False
        if blk.bbox:
            y_top = blk.bbox.y0 / max(1.0, blk.bbox.page_height)
            y_bot = blk.bbox.y1 / max(1.0, blk.bbox.page_height)
            is_top_edge = y_top <= 0.13
            is_bottom_edge = y_bot >= 0.88
            is_edge = is_top_edge or is_bottom_edge

        if PAGE_NUM_REGEX.match(txt) and (is_edge or len(txt) <= 8):
            blk.role = BlockRole.PAGE_NUMBER
            stats.running_headers_stripped += 1
            audit_log.append(
                HarnessAuditEntry(
                    stage="Pass 0: Spatial Header/Footer Filter",
                    block_id=blk.block_id,
                    page_number=blk.page_number,
                    operation="STRIP_PAGE_NUMBER",
                    before_snippet=txt,
                    after_snippet="[REMOVIDO: Número de Página]",
                    source="heuristic",
                    accepted=True,
                    reason="Numeração de página isolada detectada na margem.",
                )
            )
            continue

        fp = _normalize_header_fingerprint(txt)
        if is_edge and edge_fingerprints.get(fp, 0) >= 2 and len(txt) <= 85:
            blk.role = BlockRole.RUNNING_HEADER if is_top_edge else BlockRole.RUNNING_FOOTER
            stats.running_headers_stripped += 1
            audit_log.append(
                HarnessAuditEntry(
                    stage="Pass 0: Spatial Header/Footer Filter",
                    block_id=blk.block_id,
                    page_number=blk.page_number,
                    operation="STRIP_RUNNING_HEADER",
                    before_snippet=txt,
                    after_snippet="[REMOVIDO: Cabeçalho/Rodapé Repetitivo]",
                    source="heuristic",
                    accepted=True,
                    reason=f"Padrão repetido {edge_fingerprints[fp]}x nas margens das páginas.",
                )
            )
            continue

        # Suspected header leak in the middle of pages (e.g. broken PDF conversions)
        if edge_fingerprints.get(fp, 0) >= 3 and len(txt) <= 65:
            blk.ambiguity_flags.append(AmbiguityFlag.SUSPECTED_HEADER_LEAK)

        # Early frontmatter detection (title page, copyright, publisher)
        if not seen_first_chapter and blk.page_number <= 8 and FRONTMATTER_MARKERS_REGEX.search(txt):
            blk.role = BlockRole.FRONTMATTER
            continue

        # Footnote detection at the bottom region of the page
        if blk.bbox:
            y_rel_top = blk.bbox.y0 / max(1.0, blk.bbox.page_height)
            if y_rel_top >= 0.52 and len(txt) <= 320:
                is_footnote = bool(
                    # 1. Author citation pattern with year and page (digits or Roman numerals):
                    # e.g. Calhoun, 1992, p. 474 or Post, 1953, p. VII or Lence, 1991, p. XXIII
                    re.search(r"\b(?:[A-ZÀ-Ú][a-zà-ú]+|\d+),\s*(?:18|19|20)\d{2},\s*p(?:p)?\.\s*(?:\d+|[ivxlcdmIVXLCDM]+)", txt)
                    # 2. Footnote leading markers (digits, symbols, degree/ordinal signs, OCR glitches: $, ^, I^, 1^, °, º, ª, etc.)
                    or re.match(r"^[\$\^0-9≥\*\†\‡\•\-\—\'\°\º\ª\~]{1,5}\s*(?:[A-ZÀ-Ú]|Ibidem|Idem|Cfr|Cf|Ver\b|\d{4})", txt, re.I)
                    # 3. Canonical footnote phrasing
                    or re.match(r"^(?:Ibidem|Idem|Cfr\.|Cf\.|Ver\b|Sobre\s+isso|Apud\b|Nota\s+do)", txt, re.I)
                    # 4. Standard scholarly abbreviations, volume and page citations
                    or re.search(r"\b(?:cit\.\s+in|op\.\s*cit\.|loc\.\s*cit\.)\b", txt, re.I)
                    or re.search(r"\b(?:vol\.\s*[ivxlcdmIVXLCDM\d]+[,;]?\s*)?p(?:p)?\.\s*(?:\d+|[ivxlcdmIVXLCDM]+)", txt, re.I)
                    or re.match(r"^\d+,\s*p(?:p)?\.\s*\d+", txt)
                    # 5. Prominent author/philosopher references at bottom margin with leading digits/symbols
                    or (
                        re.search(r"\b(?:Blackburn|Hume|Smith|Millar|Locke|Marx|Kant|Burke|Tocqueville|Paine|Blackstone|Calhoun|Davis|Post|Lence|Malouet)\b", txt, re.I)
                        and re.match(r"^[\$\^0-9≥\*\†\‡\•\-\—\'\°\º\ª]", txt)
                    )
                )
                if is_footnote:
                    blk.role = BlockRole.FOOTNOTE
                    continue

        # Heading detection by regex or font size ratio
        clean_first_char = txt.lstrip("*\"' \t")[:1]
        starts_upper = clean_first_char.isupper()
        ends_with_open_punct = txt.endswith((".", ",", ";", ":", "-", "—", "–"))
        ends_with_connector = bool(
            re.search(r"\b(?:de|do|da|dos|das|em|no|na|nos|nas|com|sem|por|para|e|ou|que|o|a|os|as)\s*$", txt, re.I)
        )

        size_ratio = blk.font_size / max(1.0, body_font_size)
        if PART_REGEX.match(txt) and len(txt) <= 90:
            blk.role = BlockRole.PART_TITLE
            stats.headings_structured += 1
            seen_first_chapter = True
        elif (CHAPTER_REGEX.match(txt) or SPECIAL_SECTION_REGEX.match(txt)) and len(txt) <= 100:
            blk.role = BlockRole.CHAPTER_TITLE
            stats.headings_structured += 1
            seen_first_chapter = True
        elif size_ratio >= 1.45 and len(txt) <= 110 and starts_upper and not ends_with_open_punct and not ends_with_connector:
            if not seen_first_chapter and blk.page_number <= 6:
                # Book title on cover/half-title page
                blk.role = BlockRole.FRONTMATTER
            else:
                blk.role = BlockRole.CHAPTER_TITLE
                blk.ambiguity_flags.append(AmbiguityFlag.AMBIGUOUS_HEADING_LEVEL)
                stats.headings_structured += 1
                seen_first_chapter = True
        elif (
            len(txt) <= 65
            and starts_upper
            and not ends_with_open_punct
            and not ends_with_connector
            and (size_ratio >= 1.25 or blk.is_all_caps)
            and not re.search(r"\b(?:não|ele|ela|eles|elas|mas|porém|contudo|todavia|entretanto|quando|onde|como|porque|por\s+isso)\b", txt, re.I)
        ):
            if not seen_first_chapter and blk.page_number <= 6:
                blk.role = BlockRole.FRONTMATTER
            else:
                blk.role = BlockRole.SUBHEADING
                blk.ambiguity_flags.append(AmbiguityFlag.AMBIGUOUS_HEADING_LEVEL)
                stats.headings_structured += 1

    # 4. Flag broken paragraph boundaries across consecutive body blocks
    active_indices = [
        i
        for i, b in enumerate(blocks)
        if b.role not in {BlockRole.PAGE_NUMBER, BlockRole.RUNNING_HEADER, BlockRole.RUNNING_FOOTER}
    ]

    for pos in range(len(active_indices) - 1):
        curr_b = blocks[active_indices[pos]]
        next_b = blocks[active_indices[pos + 1]]

        if curr_b.role != BlockRole.PARAGRAPH or next_b.role != BlockRole.PARAGRAPH:
            continue

        curr_txt = curr_b.text.rstrip()
        next_txt = next_b.text.lstrip()
        if not curr_txt or not next_txt:
            continue

        # Never merge across email headers, quoted replies, or epistolographic date/salutation lines
        if (
            EMAIL_HEADER_REGEX.match(curr_txt)
            or EMAIL_HEADER_REGEX.match(next_txt)
            or EMAIL_DIVIDER_REGEX.match(curr_txt)
            or EMAIL_DIVIDER_REGEX.match(next_txt)
        ):
            continue

        # Check hyphen split at end of line
        if curr_txt.endswith(("-", "‐", "‑")) and not curr_txt.endswith("--"):
            curr_b.ambiguity_flags.append(AmbiguityFlag.HYPHENATION_SPLIT)
            curr_b.ambiguity_flags.append(AmbiguityFlag.BROKEN_PARAGRAPH_BOUNDARY)
            continue

        # Check if line does not end with terminal punctuation
        ends_open = not curr_txt.endswith(TERMINAL_PUNCTUATION)
        starts_lower = next_txt[0].islower()
        starts_dialogue = next_txt.startswith(("—", "–", "-", "“", '"', "«"))

        if (ends_open or starts_lower) and not starts_dialogue:
            curr_b.ambiguity_flags.append(AmbiguityFlag.BROKEN_PARAGRAPH_BOUNDARY)

    return blocks, body_font_size
