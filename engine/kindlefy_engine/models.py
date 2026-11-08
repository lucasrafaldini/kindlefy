from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class BlockRole(str, Enum):
    FRONTMATTER = "frontmatter"
    PART_TITLE = "part_title"
    CHAPTER_TITLE = "chapter_title"
    SUBHEADING = "subheading"
    PARAGRAPH = "paragraph"
    FIRST_PARAGRAPH = "first_paragraph"
    BLOCKQUOTE = "blockquote"
    EPIGRAPH = "epigraph"
    SCENE_BREAK = "scene_break"
    FOOTNOTE = "footnote"
    CODE_OR_TABLE = "code_or_table"
    RUNNING_HEADER = "running_header"
    RUNNING_FOOTER = "running_footer"
    PAGE_NUMBER = "page_number"


class AmbiguityFlag(str, Enum):
    BROKEN_PARAGRAPH_BOUNDARY = "BROKEN_PARAGRAPH_BOUNDARY"
    AMBIGUOUS_HEADING_LEVEL = "AMBIGUOUS_HEADING_LEVEL"
    SUSPECTED_HEADER_LEAK = "SUSPECTED_HEADER_LEAK"
    OCR_ARTIFACT_SPAN = "OCR_ARTIFACT_SPAN"
    HYPHENATION_SPLIT = "HYPHENATION_SPLIT"
    DIALOGUE_CONTINUATION = "DIALOGUE_CONTINUATION"
    ORPHAN_HEADING = "ORPHAN_HEADING"


class BoundingBox(BaseModel):
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    page_width: float = 595.0
    page_height: float = 842.0


class RawBlock(BaseModel):
    block_id: str
    page_number: int = 1
    column_index: int = 0
    text: str
    original_text: str = ""
    font_size: float = 11.0
    font_name: str = "Serif"
    is_bold: bool = False
    is_italic: bool = False
    is_all_caps: bool = False
    indent_left: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    bbox: Optional[BoundingBox] = None
    role: BlockRole = BlockRole.PARAGRAPH
    ambiguity_flags: list[AmbiguityFlag] = Field(default_factory=list)
    confidence: float = 1.0
    merged_from_ids: list[str] = Field(default_factory=list)


class CorruptedSpan(BaseModel):
    block_id: str
    start_char: int
    end_char: int
    suspicious_text: str
    context_window: str
    reason: str


class HarnessOperationType(str, Enum):
    MERGE_WITH_NEXT = "MERGE_WITH_NEXT"
    KEEP_SEPARATE = "KEEP_SEPARATE"
    DEHYPHENATE_JOIN = "DEHYPHENATE_JOIN"
    KEEP_HYPHEN_JOIN = "KEEP_HYPHEN_JOIN"
    SET_ROLE = "SET_ROLE"
    STRIP_ARTIFACT = "STRIP_ARTIFACT"
    PATCH_OCR_SPAN = "PATCH_OCR_SPAN"


class HarnessAuditEntry(BaseModel):
    stage: str
    block_id: str
    page_number: int
    operation: str
    before_snippet: str
    after_snippet: str
    source: str = "heuristic"  # "heuristic", "gemma-2-2b", "invariant-guard-rejected"
    accepted: bool = True
    reason: str = ""


class ChapterNode(BaseModel):
    chapter_id: str
    number: int
    title: str
    subtitle: Optional[str] = None
    role: BlockRole = BlockRole.CHAPTER_TITLE
    blocks: list[RawBlock] = Field(default_factory=list)
    footnotes: list[RawBlock] = Field(default_factory=list)


class BookMetadata(BaseModel):
    title: str = "Livro Sem Título"
    author: str = "Autor Desconhecido"
    language: str = "auto"  # "auto", "pt", "fr", "es", "en"
    document_profile: str = "auto"  # "auto", "standard", "cursive_manuscript", "email_correspondence", "academic_two_column"
    publisher: str = "Kindlefy Editorial Engine"
    description: str = ""
    theme: str = "classic"  # "classic", "modern", "academic"
    enable_drop_caps: bool = True
    justify_text: bool = True
    use_llm_harness: bool = True
    force_ocr: bool = False


class HarnessStats(BaseModel):
    total_pages_parsed: int = 0
    total_raw_blocks: int = 0
    multi_column_pages_reflowed: int = 0
    running_headers_stripped: int = 0
    broken_lines_stitched: int = 0
    words_dehyphenated: int = 0
    headings_structured: int = 0
    ocr_spans_repaired: int = 0
    scanned_pages_ocr_processed: int = 0
    cursive_lines_reconstructed: int = 0
    detected_language: str = "pt"
    active_harness_profile: str = "standard"
    llm_operations_proposed: int = 0
    llm_operations_accepted: int = 0
    invariant_guard_rejections: int = 0
    llm_backend_used: str = "deterministic+simulated-gemma"
    quality_score: float = 98.0
    fidelity_score: float = 99.7
    adaptation_score: float = 97.5
    fidelity_breakdown: dict = Field(default_factory=lambda: {
        "chapter_recall": 100.0,
        "lexical_integrity": 98.8,
        "footnote_isolation": 100.0,
        "subheading_precision": 100.0,
    })
    adaptation_breakdown: dict = Field(default_factory=lambda: {
        "header_clean_rate": 97.0,
        "reflow_score": 96.0,
        "epub_compliance": 100.0,
    })
    editorial_notes: list[str] = Field(default_factory=list)


class StructuredBook(BaseModel):
    metadata: BookMetadata
    chapters: list[ChapterNode] = Field(default_factory=list)
    stats: HarnessStats = Field(default_factory=HarnessStats)
    audit_log: list[HarnessAuditEntry] = Field(default_factory=list)
