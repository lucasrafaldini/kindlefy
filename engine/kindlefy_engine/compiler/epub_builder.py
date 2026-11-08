from __future__ import annotations

from datetime import datetime, timezone
import html
from pathlib import Path
import uuid
import zipfile
from lxml import etree

from kindlefy_engine.compiler.typography import generate_kindle_css, render_chapter_xhtml
from kindlefy_engine.models import StructuredBook


def _generate_cover_svg(title: str, author: str) -> str:
    t_esc = html.escape(title[:65])
    a_esc = html.escape(author[:50])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1800" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#18181b"/>
      <stop offset="100%" stop-color="#27272a"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="1800" fill="url(#bg)"/>
  <rect x="70" y="70" width="1060" height="1660" fill="none" stroke="#d4af37" stroke-width="4" opacity="0.75"/>
  <rect x="92" y="92" width="1016" height="1616" fill="none" stroke="#d4af37" stroke-width="1.5" opacity="0.45"/>
  <text x="600" y="340" text-anchor="middle" fill="#d4af37" font-family="Georgia, serif" font-size="28" letter-spacing="8">EDIÇÃO KINDLEFY</text>
  <line x1="420" y1="400" x2="780" y2="400" stroke="#d4af37" stroke-width="2" opacity="0.6"/>
  <text x="600" y="780" text-anchor="middle" fill="#fafafa" font-family="Georgia, serif" font-size="68" font-weight="bold">{t_esc}</text>
  <text x="600" y="1380" text-anchor="middle" fill="#e4e4e7" font-family="Georgia, serif" font-size="42" font-style="italic">{a_esc}</text>
  <text x="600" y="1640" text-anchor="middle" fill="#a1a1aa" font-family="Georgia, serif" font-size="22" letter-spacing="4">DIAGRAMADO COM GEMMA 2 HARNESS</text>
</svg>
"""


def build_epub(book: StructuredBook, output_path: str | Path) -> Path:
    """
    Compiles a StructuredBook into a strict EPUB 3 archive (with EPUB 2 NCX compatibility)
    optimized for Amazon Kindle (Send-to-Kindle, KFX, Paperwhite, Oasis, Scribe).
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    book_uuid = str(uuid.uuid4())
    modified_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = book.metadata

    title_esc = html.escape(meta.title)
    author_esc = html.escape(meta.author)
    lang_esc = html.escape(meta.language)

    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    titlepage_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang_esc}" lang="{lang_esc}">
<head>
  <meta charset="utf-8" />
  <title>{title_esc}</title>
  <link rel="stylesheet" type="text/css" href="../Styles/kindle.css" />
</head>
<body>
  <section class="titlepage" epub:type="titlepage">
    <h1 class="titlepage-title">{title_esc}</h1>
    <p class="titlepage-author">{author_esc}</p>
    <p class="titlepage-publisher">{html.escape(meta.publisher)}</p>
  </section>
</body>
</html>
"""

    cover_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang_esc}" lang="{lang_esc}">
<head>
  <meta charset="utf-8" />
  <title>Capa</title>
  <style type="text/css">
    body {{ margin: 0; padding: 0; text-align: center; }}
    svg {{ max-width: 100%; max-height: 98vh; }}
  </style>
</head>
<body>
  <section epub:type="cover">
    <img src="../Images/cover.svg" alt="Capa de {title_esc}" style="max-width:100%;height:auto;" />
  </section>
</body>
</html>
"""

    manifest_items = [
        '<item id="css" href="Styles/kindle.css" media-type="text/css"/>',
        '<item id="cover-img" href="Images/cover.svg" media-type="image/svg+xml" properties="cover-image"/>',
        '<item id="cover-page" href="Text/cover.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="title-page" href="Text/titlepage.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
    ]
    spine_items = [
        '<itemref idref="cover-page"/>',
        '<itemref idref="title-page"/>',
    ]
    nav_li_items: list[str] = []
    ncx_navpoints: list[str] = []

    chapter_files: list[tuple[str, str]] = []
    seen_ids: set[str] = {"css", "cover-img", "cover-page", "title-page", "nav", "ncx"}
    for idx, ch in enumerate(book.chapters, start=1):
        item_id = ch.chapter_id or f"chap_{idx}"
        if item_id in seen_ids:
            item_id = f"{item_id}_{idx}"
            ch.chapter_id = item_id
        seen_ids.add(item_id)

        fname = f"Text/{item_id}.xhtml"
        manifest_items.append(f'<item id="{item_id}" href="{fname}" media-type="application/xhtml+xml"/>')
        spine_items.append(f'<itemref idref="{item_id}"/>')

        full_label = f"{ch.title} — {ch.subtitle}" if ch.subtitle else ch.title
        label_esc = html.escape(full_label)
        nav_li_items.append(f'        <li><a href="{fname}">{label_esc}</a></li>')
        ncx_navpoints.append(
            f"""    <navPoint id="navPoint-{idx}" playOrder="{idx}">
      <navLabel><text>{label_esc}</text></navLabel>
      <content src="{fname}"/>
    </navPoint>"""
        )
        chapter_files.append((f"OEBPS/{fname}", render_chapter_xhtml(ch, meta)))

    first_chap_href = f"Text/{book.chapters[0].chapter_id}.xhtml" if book.chapters else "Text/titlepage.xhtml"

    nav_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang_esc}" lang="{lang_esc}">
<head>
  <meta charset="utf-8" />
  <title>Sumário</title>
  <link rel="stylesheet" type="text/css" href="Styles/kindle.css" />
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Sumário</h1>
    <ol>
{chr(10).join(nav_li_items)}
    </ol>
  </nav>
  <nav epub:type="landmarks" hidden="hidden">
    <h2>Marcos</h2>
    <ol>
      <li><a epub:type="cover" href="Text/cover.xhtml">Capa</a></li>
      <li><a epub:type="toc" href="nav.xhtml">Sumário</a></li>
      <li><a epub:type="bodymatter" href="{first_chap_href}">Início da Leitura</a></li>
    </ol>
  </nav>
</body>
</html>
"""

    toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_uuid}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{title_esc}</text></docTitle>
  <navMap>
{chr(10).join(ncx_navpoints)}
  </navMap>
</ncx>
"""

    content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0" xml:lang="{lang_esc}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>{title_esc}</dc:title>
    <dc:creator>{author_esc}</dc:creator>
    <dc:language>{lang_esc}</dc:language>
    <dc:publisher>{html.escape(meta.publisher)}</dc:publisher>
    <meta property="dcterms:modified">{modified_iso}</meta>
    <meta name="cover" content="cover-img"/>
  </metadata>
  <manifest>
    {chr(10) + "    ".join(manifest_items)}
  </manifest>
  <spine toc="ncx">
    {chr(10) + "    ".join(spine_items)}
  </spine>
  <guide>
    <reference type="cover" title="Capa" href="Text/cover.xhtml"/>
    <reference type="toc" title="Sumário" href="nav.xhtml"/>
    <reference type="text" title="Início" href="{first_chap_href}"/>
  </guide>
</package>
"""

    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as zf:
        # EPUB specification rule: mimetype MUST be the very first entry and uncompressed (ZIP_STORED)
        zf.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml.encode("utf-8"))
        zf.writestr("OEBPS/Styles/kindle.css", generate_kindle_css(meta).encode("utf-8"))
        zf.writestr("OEBPS/Images/cover.svg", _generate_cover_svg(meta.title, meta.author).encode("utf-8"))
        zf.writestr("OEBPS/Text/cover.xhtml", cover_xhtml.encode("utf-8"))
        zf.writestr("OEBPS/Text/titlepage.xhtml", titlepage_xhtml.encode("utf-8"))
        zf.writestr("OEBPS/nav.xhtml", nav_xhtml.encode("utf-8"))
        zf.writestr("OEBPS/toc.ncx", toc_ncx.encode("utf-8"))
        zf.writestr("OEBPS/content.opf", content_opf.encode("utf-8"))
        for path_in_zip, xhtml_str in chapter_files:
            zf.writestr(path_in_zip, xhtml_str.encode("utf-8"))

    validate_epub_archive(out)
    return out


def validate_epub_archive(epub_path: str | Path) -> dict[str, bool]:
    """
    Validates the generated EPUB archive:
    - First entry is `mimetype` with ZIP_STORED compression
    - `META-INF/container.xml` and `OEBPS/content.opf` exist
    - All XHTML documents are well-formed XML
    """
    with zipfile.ZipFile(str(epub_path), "r") as zf:
        infolist = zf.infolist()
        if not infolist or infolist[0].filename != "mimetype":
            raise ValueError("EPUB inválido: 'mimetype' deve ser o primeiro arquivo do ZIP.")
        if infolist[0].compress_type != zipfile.ZIP_STORED:
            raise ValueError("EPUB inválido: 'mimetype' deve usar compressão ZIP_STORED.")

        names = set(zf.namelist())
        if "META-INF/container.xml" not in names or "OEBPS/content.opf" not in names:
            raise ValueError("EPUB inválido: container.xml ou content.opf ausente.")

        parser = etree.XMLParser(resolve_entities=False)
        for name in names:
            if name.endswith((".xhtml", ".opf", ".ncx", ".xml")):
                etree.fromstring(zf.read(name), parser=parser)

    return {"valid": True, "mimetype_stored_first": True, "xml_well_formed": True}
