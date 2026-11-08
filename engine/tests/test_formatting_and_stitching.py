from __future__ import annotations

from kindlefy_engine.harness.orchestrator import HarnessOrchestrator
from kindlefy_engine.models import BlockRole, BoundingBox, RawBlock, BookMetadata
from kindlefy_engine.preprocess.lexical_cleaner import clean_block_lexically
from kindlefy_engine.preprocess.layout_heuristics import run_spatial_and_structural_heuristics
from kindlefy_engine.models import HarnessStats, HarnessAuditEntry


def test_lexical_cleaner_corruptions():
    audit_log = []
    # Test OCR typos
    b1 = RawBlock(block_id="B01", page_number=1, text='paecem responder e ceebram o cquilíbrio na mctade do século XIX com o plebcu pro-prietários')
    clean1 = clean_block_lexically(b1, audit_log)
    assert 'parecem responder e celebram o equilíbrio na metade do século XIX' in clean1.text
    assert 'plebeu' in clean1.text
    assert 'proprietários' in clean1.text
    assert 'pro-prietários' not in clean1.text

    # Test corrupted quotes & asterisks
    b2 = RawBlock(block_id="B02", page_number=1, text='opinião e religião"\'s e os * governos absolutos"')
    clean2 = clean_block_lexically(b2, audit_log)
    assert 'religião"' in clean2.text
    assert '"\'s' not in clean2.text
    assert '* governos' not in clean2.text

    # Test hyphen resolution: pro- + prietários must dehyphenate
    from kindlefy_engine.preprocess.lexical_cleaner import resolve_hyphen_split
    joined, was_dehyphenated = resolve_hyphen_split("pro-", "prietários")
    assert joined == "proprietários"
    assert was_dehyphenated is True


def test_footnote_detection_and_isolation():
    stats = HarnessStats()
    audit_log = []

    # Footnote with $ sign and citation
    fn1 = RawBlock(
        block_id="B10",
        page_number=6,
        text="$ Calhoun, 1992, p. 474.",
        font_size=8.5,
        bbox=BoundingBox(x0=50, y0=700, x1=300, y1=715, page_width=595, page_height=842),
    )
    # Footnote with degree sign and Roman numeral page: ° Post, 1953, p. VII.
    fn2 = RawBlock(
        block_id="B11",
        page_number=6,
        text="° Post, 1953, p. VII.",
        font_size=8.5,
        bbox=BoundingBox(x0=50, y0=720, x1=300, y1=735, page_width=595, page_height=842),
    )
    # Footnote with ordinal: 1° Lence, 1991, p. XXIII.
    fn3 = RawBlock(
        block_id="B12",
        page_number=6,
        text="1° Lence, 1991, p. XXIII.",
        font_size=8.5,
        bbox=BoundingBox(x0=50, y0=735, x1=300, y1=750, page_width=595, page_height=842),
    )
    # Footnote with volume: 1, p. 240, 250; vol. III, p. 593.
    fn4 = RawBlock(
        block_id="B13",
        page_number=6,
        text="1, p. 240, 250; vol. III, p. 593.",
        font_size=8.5,
        bbox=BoundingBox(x0=50, y0=750, x1=300, y1=765, page_width=595, page_height=842),
    )
    # Regular body paragraph
    para = RawBlock(
        block_id="B14",
        page_number=6,
        text="Este é um parágrafo normal de texto corrente.",
        font_size=11.0,
        bbox=BoundingBox(x0=50, y0=200, x1=500, y1=250, page_width=595, page_height=842),
    )

    blocks, _ = run_spatial_and_structural_heuristics([para, fn1, fn2, fn3, fn4], stats, audit_log)
    assert blocks[0].role == BlockRole.PARAGRAPH
    assert blocks[1].role == BlockRole.FOOTNOTE
    assert blocks[2].role == BlockRole.FOOTNOTE
    assert blocks[3].role == BlockRole.FOOTNOTE
    assert blocks[4].role == BlockRole.FOOTNOTE


def test_subordinated_orphan_comma_stitching():
    orch = HarnessOrchestrator()
    stats = HarnessStats()
    audit_log = []

    b1 = RawBlock(
        block_id="B20",
        page_number=4,
        text='...que celebram Calhoun como "um distinto individualista"',
        role=BlockRole.PARAGRAPH,
    )
    b2 = RawBlock(
        block_id="B21",
        page_number=4,
        text=', como um campeão da "defesa dos direitos da minoria"',
        role=BlockRole.PARAGRAPH,
    )
    b3 = RawBlock(
        block_id="B22",
        page_number=4,
        text=', isto é, como um teórico do senso do equilíbrio',
        role=BlockRole.PARAGRAPH,
    )

    stitched = orch._execute_pass2_stitching([b1, b2, b3], use_llm=False, stats=stats, audit_log=audit_log)
    assert len(stitched) == 1
    # Check that comma is directly attached without space before it
    assert 'individualista", como um campeão' in stitched[0].text
    assert 'minoria", isto é, como um teórico' in stitched[0].text


def test_mid_sentence_fragment_not_subheading():
    stats = HarnessStats()
    audit_log = []
    orch = HarnessOrchestrator()

    b1 = RawBlock(
        block_id="B30",
        page_number=5,
        text='Juntamente com os "governos absolutos" e o conceito de',
        role=BlockRole.PARAGRAPH,
    )
    # This was previously promoted or treated as subheading because it had no period
    b2 = RawBlock(
        block_id="B31",
        page_number=5,
        text='*cruzada ele não cansa de criticar e condenar o fanatismo',
        font_size=13.5, # Slightly larger or bold
        role=BlockRole.PARAGRAPH,
    )
    b3 = RawBlock(
        block_id="B32",
        page_number=5,
        text=', aos quais contrapõe o "compromisso" como princípio',
        role=BlockRole.PARAGRAPH,
    )

    blocks, _ = run_spatial_and_structural_heuristics([b1, b2, b3], stats, audit_log)
    # Ensure b2 was NOT promoted to SUBHEADING or CHAPTER_TITLE
    assert blocks[1].role == BlockRole.PARAGRAPH
    assert not blocks[1].text.startswith('*')

    # Now stitch them together
    stitched = orch._execute_pass2_stitching(blocks, use_llm=False, stats=stats, audit_log=audit_log)
    assert len(stitched) == 1
    assert 'conceito de cruzada ele não cansa de criticar e condenar o fanatismo, aos quais contrapõe' in stitched[0].text


def test_narrative_sentence_not_matched_to_toc_section():
    from kindlefy_engine.preprocess.toc_detector import (
        CanonicalTOCItem,
        TOCDetectionResult,
        match_block_to_toc,
        normalize_text_for_matching,
    )

    t_sec1 = "A revolução americana e a revolução francesa"
    t_sec2 = "O tratamento do liberalismo no século XIX"

    toc_res = TOCDetectionResult(
        found=True,
        start_page=9,
        end_page=12,
        canonical_sections=[
            CanonicalTOCItem(number=1, title=t_sec1, normalized_title=normalize_text_for_matching(t_sec1), page_hint="25"),
            CanonicalTOCItem(number=2, title=t_sec2, normalized_title=normalize_text_for_matching(t_sec2), page_hint="40"),
        ],
    )

    # Narrative sentences that previously caused false subheading bolding
    t1 = "revolução francesa, e de orientação liberal garantida, não hesitam em definir"
    t2 = "século XIX? Contra esse tratamento diferente iria reagir com indignação o"
    t3 = "revolução americana (Common Sense as Paine, no opúsculo mais célebre da"

    m1, k1 = match_block_to_toc(t1, toc_res)
    m2, k2 = match_block_to_toc(t2, toc_res)
    m3, k3 = match_block_to_toc(t3, toc_res)

    assert k1 == "none"
    assert k2 == "none"
    assert k3 == "none"

    # Real standalone section heading with capital letter
    real_sec = "A revolução americana e a revolução francesa"
    m_real, k_real = match_block_to_toc(real_sec, toc_res)
    assert k_real == "section"
    assert m_real.number == 1


