from __future__ import annotations

import html
import re
from kindlefy_engine.models import BlockRole, BookMetadata, ChapterNode


def generate_kindle_css(meta: BookMetadata) -> str:
    """
    Generates a Kindle-optimized stylesheet supporting EPUB 3, KF8 (AZW3/KFX),
    and legacy MOBI7 media queries, with widow/orphan protection and chapter ornaments.
    """
    if meta.theme == "modern":
        font_family = '"Amazon Ember", "Helvetica Neue", Arial, sans-serif'
        heading_font = '"Amazon Ember", "Helvetica Neue", sans-serif'
        line_height = "1.58"
    elif meta.theme == "academic":
        font_family = '"Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
        heading_font = '"Helvetica Neue", Arial, sans-serif'
        line_height = "1.52"
    else:
        # Classic Literary (Bookerly / Baskerville)
        font_family = 'Bookerly, Baskerville, "EB Garamond", Palatino, Georgia, serif'
        heading_font = 'Bookerly, Baskerville, Georgia, serif'
        line_height = "1.62"

    text_align = "justify" if meta.justify_text else "left"

    return f"""@charset "UTF-8";

@namespace epub "http://www.idpf.org/2007/ops";

@page {{
  margin-top: 1.2em;
  margin-bottom: 1.2em;
}}

body {{
  font-family: {font_family};
  line-height: {line_height};
  margin: 0;
  padding: 0 3%;
  widows: 2;
  orphans: 2;
  -webkit-hyphens: auto;
  hyphens: auto;
}}

/* Chapter Header & Pagination Control */
section.chapter {{
  page-break-before: always;
  break-before: page;
}}

header.chapter-header {{
  margin-top: 14%;
  margin-bottom: 2.4em;
  text-align: center;
  page-break-inside: avoid;
  break-inside: avoid;
  page-break-after: avoid;
  break-after: avoid;
}}

.chapter-number-ornament {{
  font-family: {heading_font};
  font-size: 0.78em;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  opacity: 0.72;
  margin-bottom: 0.6em;
  display: block;
}}

h1.chapter-title {{
  font-family: {heading_font};
  font-size: 1.65em;
  font-weight: 700;
  line-height: 1.25;
  margin: 0.2em 0 0.4em 0;
  text-align: center;
  page-break-after: avoid;
  break-after: avoid;
}}

h1.part-title {{
  font-family: {heading_font};
  font-size: 2.0em;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 22% 0 0.6em 0;
  text-align: center;
}}

p.chapter-subtitle {{
  font-family: {heading_font};
  font-size: 1.08em;
  font-style: italic;
  margin: 0.3em 0 0 0;
  opacity: 0.85;
  text-align: center;
}}

.chapter-rule {{
  width: 28%;
  height: 1px;
  border: 0;
  border-top: 1px solid currentColor;
  opacity: 0.35;
  margin: 1.2em auto 0 auto;
}}

h2.subheading {{
  font-family: {heading_font};
  font-size: 1.22em;
  font-weight: 600;
  margin: 1.8em 0 0.6em 0;
  text-align: left;
  text-indent: 0;
  page-break-after: avoid;
  break-after: avoid;
}}

/* Body Paragraphs */
p {{
  margin: 0;
  text-indent: 1.45em;
  text-align: {text_align};
  widows: 2;
  orphans: 2;
}}

p.first-para {{
  text-indent: 0;
  margin-top: 0.4em;
}}

span.dropcap {{
  float: left;
  font-size: 3.1em;
  line-height: 0.82;
  padding-top: 0.04em;
  padding-right: 0.1em;
  padding-bottom: 0.02em;
  font-weight: 700;
}}

span.lead-words {{
  font-variant: small-caps;
  letter-spacing: 0.05em;
}}

/* Epigraph & Blockquote */
blockquote.epigraph {{
  margin: 0 8% 2.0em 18%;
  font-style: italic;
  font-size: 0.94em;
  text-align: right;
  page-break-inside: avoid;
  break-inside: avoid;
}}

blockquote.editorial-quote {{
  margin: 1.1em 6%;
  padding-left: 0.9em;
  border-left: 2px solid currentColor;
  font-style: italic;
  font-size: 0.95em;
}}

blockquote p {{
  text-indent: 0;
  text-align: left;
}}

/* Scene Break */
div.scene-break {{
  text-align: center;
  margin: 1.6em 0;
  letter-spacing: 0.45em;
  font-size: 0.95em;
  text-indent: 0;
  page-break-inside: avoid;
  break-inside: avoid;
}}

/* Table of Contents Formatting */
p.toc-entry {{
  margin: 0.7em 0;
  text-indent: 0;
  font-size: 1.05em;
  line-height: 1.45;
  page-break-inside: avoid;
  break-inside: avoid;
}}

/* Chapter Footnotes Section */
.chapter-footnotes {{
  margin-top: 3.5em;
  padding-top: 1.2em;
  page-break-inside: avoid;
  break-inside: avoid;
}}

.footnote-rule {{
  width: 32%;
  margin: 0 0 1.2em 0;
  border: 0;
  border-top: 1px solid currentColor;
  opacity: 0.35;
}}

.footnote-list {{
  list-style-type: none;
  margin: 0;
  padding: 0;
  font-size: 0.85em;
  line-height: 1.48;
  opacity: 0.85;
}}

.footnote-item {{
  margin-bottom: 0.6em;
  text-indent: 0;
  text-align: left;
}}

.fn-num {{
  font-weight: 700;
  margin-right: 0.3em;
}}

/* Title Page */
section.titlepage {{
  text-align: center;
  margin-top: 18%;
  page-break-after: always;
  break-after: page;
}}

.titlepage-title {{
  font-size: 2.2em;
  font-weight: 700;
  margin-bottom: 0.4em;
}}

.titlepage-author {{
  font-size: 1.2em;
  font-style: italic;
  opacity: 0.85;
  margin-bottom: 3em;
}}

.titlepage-publisher {{
  font-size: 0.8em;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  opacity: 0.65;
  margin-top: 30%;
}}

@media amzn-mobi {{
  span.dropcap {{
    font-size: 1.4em;
    font-weight: bold;
  }}
}}
"""


def _format_first_paragraph_inner(text: str, enable_drop_caps: bool) -> str:
    escaped = html.escape(text.strip())
    if not escaped or not enable_drop_caps:
        return escaped

    # Don't apply drop-cap if paragraph starts with a quote, dash, symbol, or digit (e.g. "2 a edicao")
    if escaped[0].isdigit() or escaped[0] in {'"', "'", "—", "–", "-", "“", "«", "*", "✦", "•"}:
        return escaped

    first_char = escaped[0]
    rest = escaped[1:]
    words = rest.split(" ", 3)
    if len(words) >= 3:
        lead = " ".join(words[:2])
        tail = " ".join(words[2:])
        return f'<span class="dropcap">{first_char}</span><span class="lead-words">{lead}</span> {tail}'
    return f'<span class="dropcap">{first_char}</span>{rest}'


def render_chapter_xhtml(chapter: ChapterNode, meta: BookMetadata) -> str:
    """Renders a ChapterNode into strict XHTML 1.1 / EPUB 3 document."""
    title_esc = html.escape(chapter.title)
    subtitle_html = (
        f'\n      <p class="chapter-subtitle">{html.escape(chapter.subtitle)}</p>'
        if chapter.subtitle
        else ""
    )
    heading_class = (
        "part-title"
        if chapter.role == BlockRole.PART_TITLE
        else "frontmatter-title"
        if chapter.role == BlockRole.FRONTMATTER
        else "chapter-title"
    )
    is_special_section = (
        chapter.role in {BlockRole.PART_TITLE, BlockRole.FRONTMATTER}
        or bool(re.match(r"^(?:sum[áa]rio|índice|indice|conteúdo|table of contents|contents)\b", chapter.title, re.I))
    )
    ornament_html = (
        f'<span class="chapter-number-ornament">✦ {chapter.number:02d} ✦</span>\n      '
        if not is_special_section
        else ""
    )
    allow_drop_caps = meta.enable_drop_caps and not is_special_section

    body_parts: list[str] = []
    is_toc_chapter = (
        chapter.chapter_id == "toc"
        or bool(re.match(r"^(?:sum[áa]rio|índice|indice)\b", chapter.title, re.I))
    )

    for blk in chapter.blocks:
        txt = blk.text.strip()
        if not txt:
            continue
        esc = html.escape(txt)

        if is_toc_chapter:
            body_parts.append(f'    <p class="toc-entry">{esc}</p>')
        elif blk.role == BlockRole.SUBHEADING:
            body_parts.append(f'    <h2 class="subheading">{esc}</h2>')
        elif blk.role == BlockRole.EPIGRAPH:
            body_parts.append(f'    <blockquote class="epigraph"><p>{esc}</p></blockquote>')
        elif blk.role == BlockRole.BLOCKQUOTE:
            body_parts.append(f'    <blockquote class="editorial-quote"><p>{esc}</p></blockquote>')
        elif blk.role == BlockRole.SCENE_BREAK:
            body_parts.append('    <div class="scene-break" role="separator">✦ ✦ ✦</div>')
        elif blk.role == BlockRole.FIRST_PARAGRAPH:
            inner = _format_first_paragraph_inner(txt, allow_drop_caps)
            body_parts.append(f'    <p class="first-para">{inner}</p>')
        else:
            body_parts.append(f"    <p>{esc}</p>")

    if chapter.footnotes:
        fn_items: list[str] = []
        for fn_idx, fn_b in enumerate(chapter.footnotes):
            fn_clean = re.sub(r"^[0-9≥\*\†\‡\•\-\—\']+\s*", "", fn_b.text.strip())
            fn_items.append(
                f'      <li class="footnote-item"><span class="fn-num">{fn_idx + 1}.</span> {html.escape(fn_clean)}</li>'
            )
        footnotes_html = f"""    <aside class="chapter-footnotes" epub:type="footnotes">
      <hr class="footnote-rule" />
      <ol class="footnote-list">
{"\n".join(fn_items)}
      </ol>
    </aside>"""
        body_parts.append(footnotes_html)

    paragraphs_joined = "\n".join(body_parts)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{html.escape(meta.language)}" lang="{html.escape(meta.language)}">
<head>
  <meta charset="utf-8" />
  <title>{title_esc}</title>
  <link rel="stylesheet" type="text/css" href="../Styles/kindle.css" />
</head>
<body>
  <section class="chapter" epub:type="chapter" id="{chapter.chapter_id}">
    <header class="chapter-header">
      {ornament_html}<h1 class="{heading_class}">{title_esc}</h1>{subtitle_html}
      <hr class="chapter-rule" />
    </header>
{paragraphs_joined}
  </section>
</body>
</html>
"""
