from __future__ import annotations

import html
from pathlib import Path
import random
import shutil
import struct
import subprocess
import time

from kindlefy_engine.models import BlockRole, StructuredBook


def _render_mobi_html(book: StructuredBook) -> bytes:
    """
    Renders a Kindle MOBI6/HTML3.2+Kindle-tags compatible stream with
    <mbp:pagebreak/>, inline table of contents, and chapter formatting.
    """
    meta = book.metadata
    t_esc = html.escape(meta.title)
    a_esc = html.escape(meta.author)

    parts: list[str] = [
        "<html><head>",
        f"<title>{t_esc}</title>",
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />',
        "<style>",
        "body { font-family: serif; line-height: 1.5; }",
        "h1 { text-align: center; margin-top: 1.5em; margin-bottom: 0.4em; }",
        "h2 { margin-top: 1.2em; margin-bottom: 0.4em; }",
        "p { text-indent: 1.4em; margin-top: 0; margin-bottom: 0; text-align: justify; }",
        "p.first { text-indent: 0; }",
        "blockquote { margin-left: 1.5em; font-style: italic; }",
        "div.scenebreak { text-align: center; margin: 1.2em 0; }",
        "</style>",
        "</head><body>",
        f'<div align="center"><h1>{t_esc}</h1><p class="first"><i>{a_esc}</i></p></div>',
        "<mbp:pagebreak/>",
        '<a name="toc"></a><h2>Sumário</h2><ul>',
    ]

    for ch in book.chapters:
        label = f"{ch.title} — {ch.subtitle}" if ch.subtitle else ch.title
        parts.append(f'<li><a href="#{ch.chapter_id}">{html.escape(label)}</a></li>')
    parts.append("</ul><mbp:pagebreak/>")

    for ch in book.chapters:
        parts.append(f'<a name="{ch.chapter_id}"></a>')
        parts.append(f"<h1>{html.escape(ch.title)}</h1>")
        if ch.subtitle:
            parts.append(f'<p class="first" align="center"><i>{html.escape(ch.subtitle)}</i></p>')
        parts.append("<hr/>")

        for blk in ch.blocks:
            esc = html.escape(blk.text.strip())
            if not esc:
                continue
            if blk.role == BlockRole.SUBHEADING:
                parts.append(f"<h2>{esc}</h2>")
            elif blk.role in {BlockRole.EPIGRAPH, BlockRole.BLOCKQUOTE}:
                parts.append(f"<blockquote>{esc}</blockquote>")
            elif blk.role == BlockRole.SCENE_BREAK:
                parts.append('<div class="scenebreak">* * *</div>')
            elif blk.role == BlockRole.FIRST_PARAGRAPH:
                parts.append(f'<p class="first">{esc}</p>')
            else:
                parts.append(f"<p>{esc}</p>")

        parts.append("<mbp:pagebreak/>")

    parts.append("</body></html>")
    return "\n".join(parts).encode("utf-8")


def _build_exth_header(title: str, author: str, publisher: str, lang: str) -> bytes:
    """Builds a standard Kindle EXTH metadata block (Author=100, Publisher=101, Title=503, Lang=524)."""
    records: list[tuple[int, bytes]] = [
        (100, author.encode("utf-8")),
        (101, publisher.encode("utf-8")),
        (503, title.encode("utf-8")),
        (524, lang.encode("utf-8")),
    ]
    rec_bytes = b""
    for rtype, payload in records:
        rlen = 8 + len(payload)
        rec_bytes += struct.pack(">II", rtype, rlen) + payload

    total_len = 12 + len(rec_bytes)
    exth = b"EXTH" + struct.pack(">II", total_len, len(records)) + rec_bytes
    # Pad to 4-byte boundary
    pad = (4 - (len(exth) % 4)) % 4
    return exth + (b"\x00" * pad)


def build_mobi(book: StructuredBook, output_path: str | Path, epub_path: Path | None = None) -> Path:
    """
    Compiles a Kindle .mobi file.
    1. If `ebook-convert` (Calibre) is installed and epub_path is provided, uses it if requested.
    2. Built-in native PalmDOC/MOBI6 + EXTH binary packager works 100% standalone across
       Windows, macOS, and Linux with zero external dependencies.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ebook_convert = shutil.which("ebook-convert")
    if ebook_convert and epub_path and epub_path.exists():
        try:
            subprocess.run(
                [ebook_convert, str(epub_path), str(out)],
                check=True,
                capture_output=True,
                timeout=60,
            )
            if out.exists() and out.stat().st_size > 512:
                return out
        except Exception:
            pass

    # Standalone Native PalmDOC / MOBI6 Binary Builder
    html_bytes = _render_mobi_html(book)
    chunk_size = 4096
    text_records = [
        html_bytes[i : i + chunk_size] for i in range(0, len(html_bytes), chunk_size)
    ]
    if not text_records:
        text_records = [b"<html><body></body></html>"]

    meta = book.metadata
    title_bytes = meta.title.encode("utf-8")
    exth_block = _build_exth_header(meta.title, meta.author, meta.publisher, meta.language)

    # PalmDOC Header (16 bytes)
    # Compression=1 (No compression, universally supported by all MOBI readers),
    # TextLength, RecordCount, RecordSize=4096, EncryptionType=0
    palmdoc_header = struct.pack(
        ">HHIHHHH",
        1,  # compression: 1 = raw/none
        0,  # unused
        len(html_bytes),
        len(text_records),
        4096,
        0,  # encryption: 0 = none
        0,
    )

    # MOBI Header (232 bytes standard v6)
    mobi_header_len = 232
    full_name_offset = 16 + mobi_header_len + len(exth_block)
    uid = random.randint(10000, 99999999)

    mobi_header = bytearray(mobi_header_len)
    mobi_header[0:4] = b"MOBI"
    struct.pack_into(">I", mobi_header, 4, mobi_header_len)  # header length
    struct.pack_into(">I", mobi_header, 8, 2)  # mobi type: 2 = BOOK
    struct.pack_into(">I", mobi_header, 12, 65001)  # text encoding: 65001 = UTF-8
    struct.pack_into(">I", mobi_header, 16, uid)  # unique id
    struct.pack_into(">I", mobi_header, 20, 6)  # file version 6
    # Unused index pointers (0xFFFFFFFF) from offset 24 to 64
    for off in range(24, 64, 4):
        struct.pack_into(">I", mobi_header, off, 0xFFFFFFFF)
    struct.pack_into(">I", mobi_header, 64, len(text_records) + 1)  # first non-book index
    struct.pack_into(">I", mobi_header, 68, full_name_offset)  # full name offset
    struct.pack_into(">I", mobi_header, 72, len(title_bytes))  # full name length
    struct.pack_into(">I", mobi_header, 76, 1046)  # locale (pt-BR = 1046)
    struct.pack_into(">I", mobi_header, 92, 6)  # min version
    struct.pack_into(">I", mobi_header, 96, len(text_records) + 1)  # first image index
    struct.pack_into(">I", mobi_header, 112, 0x40)  # EXTH flags: bit 6 (0x40) indicates EXTH present
    struct.pack_into(">H", mobi_header, 176, 1)  # first content record number
    struct.pack_into(">H", mobi_header, 178, len(text_records))  # last content record number
    struct.pack_into(">I", mobi_header, 180, 1)

    record0 = bytes(palmdoc_header) + bytes(mobi_header) + exth_block + title_bytes
    pad_r0 = (4 - (len(record0) % 4)) % 4
    record0 += b"\x00" * (pad_r0 + 8)

    eof_record = b"\xe9\x8e\r\n"
    all_records = [record0] + text_records + [eof_record]
    num_records = len(all_records)

    # PDB Header (78 bytes) + 8 bytes per record entry + 2 bytes gap
    pdb_name = meta.title.encode("ascii", errors="ignore")[:31].ljust(32, b"\x00")
    now_ts = int(time.time())
    pdb_header = struct.pack(
        ">32sHHIIIIII4s4sIIH",
        pdb_name,
        0,
        0,
        now_ts,
        now_ts,
        0,
        0,
        0,
        0,
        b"BOOK",
        b"MOBI",
        0,
        0,
        num_records,
    )

    header_size = 78 + (num_records * 8) + 2
    rec_table = bytearray()
    current_offset = header_size
    for idx, rec in enumerate(all_records):
        rec_table += struct.pack(">II", current_offset, idx)
        current_offset += len(rec)

    with open(out, "wb") as f:
        f.write(pdb_header)
        f.write(rec_table)
        f.write(b"\x00\x00")
        for rec in all_records:
            f.write(rec)

    return out
