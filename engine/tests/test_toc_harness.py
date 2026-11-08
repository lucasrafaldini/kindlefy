import pytest
from kindlefy_engine.models import (
    BlockRole,
    BookMetadata,
    HarnessAuditEntry,
    HarnessStats,
    RawBlock,
)
from kindlefy_engine.preprocess.toc_detector import (
    detect_and_extract_toc,
    match_block_to_toc,
)
from kindlefy_engine.harness.orchestrator import HarnessOrchestrator


def test_losurdo_toc_detection_and_matching():
    stats = HarnessStats()
    audit: list[HarnessAuditEntry] = []

    # Simulate blocks from Losurdo scan
    blocks = [
        # Frontmatter
        RawBlock(
            block_id="b_p1_1",
            page_number=1,
            text="CONTRA-HISTORIA DO LIBERALISMO\nDomenico Losurdo",
            font_size=24.0,
            role=BlockRole.PARAGRAPH,
        ),
        RawBlock(
            block_id="b_p2_1",
            page_number=2,
            text="EDITORA IDEIAS & LETRAS\nISBN 88-420-7717-8",
            font_size=11.0,
            role=BlockRole.PARAGRAPH,
        ),
        # TOC Page
        RawBlock(
            block_id="b_p3_1",
            page_number=3,
            text="Sumario\nUma brevepremissametodologica-11\n1.Oqueéoliberalismo?-13\n1. Um conjunto de perguntas constrangedoras, p. 13 - 2.A revolucao americana e a revelacao de uma verdade constrangedora,p.19-3. O papel da cscravidao cntre os dois lados doAtlantico,p.24-4.Holanda,Inglaterra, America,p.27\n11.Liberalismo e escravidao racial: um singular parto gemco - 47",
            font_size=12.0,
            role=BlockRole.PARAGRAPH,
        ),
        # Body Chapter 1
        RawBlock(
            block_id="b_p11_1",
            page_number=11,
            text="Uma breve premissa metodológica",
            font_size=18.0,
            role=BlockRole.CHAPTER_TITLE,
        ),
        RawBlock(
            block_id="b_p11_2",
            page_number=11,
            text="Em que consiste a diferença deste livro das histórias do liberalismo já publicadas?",
            font_size=12.0,
            role=BlockRole.PARAGRAPH,
        ),
        # Body Chapter 2
        RawBlock(
            block_id="b_p13_1",
            page_number=13,
            text="1. O que é o liberalismo?",
            font_size=18.0,
            role=BlockRole.CHAPTER_TITLE,
        ),
        # Body Sub-section inside Chapter 2 (erroneously tagged as CHAPTER_TITLE by font-size heuristic in OCR)
        RawBlock(
            block_id="b_p19_1",
            page_number=19,
            text="revolução americana (Common Sense as Painc, no opusculo mais célebre da",
            font_size=16.0,
            role=BlockRole.CHAPTER_TITLE,
        ),
        # Body OCR artifact (erroneously tagged as CHAPTER_TITLE)
        RawBlock(
            block_id="b_p20_1",
            page_number=20,
            text="isso não é tudo. Juntamente com...",
            font_size=16.0,
            role=BlockRole.CHAPTER_TITLE,
        ),
    ]

    toc_res = detect_and_extract_toc(blocks, stats, audit)

    assert toc_res.found is True
    assert toc_res.start_page == 3
    assert len(toc_res.canonical_chapters) >= 3

    # Check chapter titles extracted
    ch_titles = [c.normalized_title for c in toc_res.canonical_chapters]
    assert any("premissa" in t for t in ch_titles)
    assert any("liberalismo" in t for t in ch_titles)

    # Check matching logic
    item_ch1, kind1 = match_block_to_toc("Uma breve premissa metodológica", toc_res)
    assert kind1 == "chapter"

    item_ch2, kind2 = match_block_to_toc("1. O que é o liberalismo?", toc_res)
    assert kind2 == "chapter"

    # Real canonical section title from the Sumário
    real_sec = "2. A revolução americana e a revelação de uma verdade constrangedora"
    item_sec, kind_sec = match_block_to_toc(real_sec, toc_res)
    assert kind_sec == "section"

    # Running prose fragment mentioning 'revolução americana' must NOT be classified as section
    item_frag, kind_frag = match_block_to_toc("revolução americana (Common Sense as Painc, no opusculo mais célebre da", toc_res)
    assert kind_frag == "none"

    item_none, kind_none = match_block_to_toc("isso não é tudo. Juntamente com...", toc_res)
    assert kind_none == "none"

    # Now verify alignment demotions on active blocks
    for blk in blocks:
        if blk.page_number <= toc_res.end_page:
            blk.role = BlockRole.FRONTMATTER
            continue
        m_item, m_kind = match_block_to_toc(blk.text, toc_res)
        if m_kind == "chapter":
            blk.role = BlockRole.CHAPTER_TITLE
        elif m_kind == "section":
            blk.role = BlockRole.SUBHEADING
        elif blk.role in {BlockRole.CHAPTER_TITLE, BlockRole.PART_TITLE}:
            blk.role = BlockRole.PARAGRAPH

    orchestrator = HarnessOrchestrator()
    meta = BookMetadata(title="Contra-História do Liberalismo", author="Domenico Losurdo")
    chapters = orchestrator._assemble_chapters_and_pagination(blocks, meta, stats, audit, toc_result=toc_res)

    assert blocks[3].role == BlockRole.CHAPTER_TITLE  # Uma breve premissa metodológica
    assert blocks[5].role == BlockRole.CHAPTER_TITLE  # 1. O que é o liberalismo?
    assert blocks[6].role in {BlockRole.PARAGRAPH, BlockRole.FIRST_PARAGRAPH}  # revolução americana (narrativa mantida como parágrafo)
    assert blocks[7].role == BlockRole.PARAGRAPH      # isso não é tudo (mantido como parágrafo)

    # Expected:
    # 0: Abertura (p1, p2)
    # 0: Sumário (p3)
    # 1: Uma breve premissa metodológica (p11)
    # 2: 1. O que é o liberalismo? (p13, containing subheading p19 and paragraph p20)
    titles = [ch.title for ch in chapters]
    assert "Abertura" in titles
    assert "Sumário" in titles
    assert "Uma breve premissa metodológica" in titles
    assert "1. O que é o liberalismo?" in titles
    # Ensure bogus blocks were NOT made into chapters
    assert not any("revolução americana" in t for t in titles)
    assert not any("isso não é tudo" in t for t in titles)

