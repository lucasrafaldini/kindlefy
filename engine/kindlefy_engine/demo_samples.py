from __future__ import annotations

from pathlib import Path
import pymupdf as fitz


def create_torture_test_pdf(output_path: str | Path) -> Path:
    """
    Generates a realistic 'Torture Test' PDF containing:
    - Page 1: Chapter 1 with repeating running header, page number, broken line wraps,
      syllable hyphenation ('desenvol-\\nvimento'), compound hyphenation ('guarda-\\nchuva'),
      and OCR glitches ('c0nhecimen1o', 'pensamen1o') plus a protected technical token ('MP3').
    - Page 2: Mid-sentence page crossing from Page 1, dialogue turns, scene break, and Chapter 2
      with a two-column layout to test XY-Cut column reflow.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    # PAGE 1: Single-column with broken PDF lines, running header/footer, hyphens, OCR spans
    p1 = doc.new_page(width=595, height=842)
    # Running header
    p1.insert_text((72, 42), "CRÔNICAS DO HORIZONTE PERDIDO - EDIÇÃO DE PROVA", fontsize=8.5, fontname="helv")
    # Chapter title + subtitle
    p1.insert_text((180, 120), "Capítulo 1", fontsize=20, fontname="tiro")
    p1.insert_text((175, 148), "O Labirinto de Papel", fontsize=14, fontname="tiit")

    # Epigraph
    p1.insert_text(
        (140, 185),
        "\"A memória dos livros sobrevive mesmo quando as páginas se partem.\"",
        fontsize=10.5,
        fontname="tiit",
    )

    # Broken paragraph 1 (with syllable hyphenation & compound hyphenation & OCR glitch)
    lines_p1 = [
        (72, 230, "Naquela manhã de outono, o velho tipógrafo observava o desenvol-"),
        (72, 246, "vimento silencioso da neblina sobre os telhados da cidade antiga, segurando"),
        (72, 262, "seu guarda-"),
        (72, 278, "chuva escuro enquanto buscava preservar todo o c0nhecimen1o acumulado"),
        (72, 294, "nas oficinas de impressão que ainda resistiam ao esquecimento."),
        # Paragraph 2 with dialogue & protected acronym MP3
        (86, 330, "Ele abriu o caderno de notas onde guardava cada pensamen1o raro e mesmo"),
        (72, 346, "um gravador MP3 antigo para registrar as histórias dos mestres encadernadores."),
        (86, 375, "- Você acredita que as máquinas entenderão o ritmo da prosa? - perguntou"),
        (72, 391, "Helena, aproximando-se da bancada iluminada pela lâmpada de latão."),
        (86, 418, "- Somente se ensinarmos a elas onde respira cada parágrafo e onde"),
    ]
    for x, y, text in lines_p1:
        p1.insert_text((x, y), text, fontsize=11.0, fontname="tiro")

    # Running footer / page number
    p1.insert_text((285, 805), "- 1 -", fontsize=9.0, fontname="helv")

    # PAGE 2: Page-crossing continuation + Scene Break + Chapter 2 in 2-Column Layout
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((72, 42), "CRÔNICAS DO HORIZONTE PERDIDO - EDIÇÃO DE PROVA", fontsize=8.5, fontname="helv")

    # Continuation of the unfinished sentence at the bottom of Page 1!
    p2.insert_text(
        (72, 95),
        "termina o silêncio entre um capítulo e outro - respondeu o mestre com serenidade.",
        fontsize=11.0,
        fontname="tiro",
    )
    p2.insert_text((260, 125), "* * *", fontsize=11.0, fontname="tiro")

    # Chapter 2 header spanning full width
    p2.insert_text((210, 165), "Capítulo 2", fontsize=20, fontname="tiro")
    p2.insert_text((185, 192), "As Duas Colunas do Tempo", fontsize=14, fontname="tiit")

    # Left Column (x = 60..270)
    left_col = [
        (60, 235, "Quando os primeiros tratados foram"),
        (60, 250, "impressos em duas colunas estreitas,"),
        (60, 265, "muitos leitores temiam que o olhar"),
        (60, 280, "saltasse de uma margem à outra sem"),
        (60, 295, "encontrar o fio condutor da narrativa."),
    ]
    # Right Column (x = 315..530)
    right_col = [
        (315, 235, "Contudo, a geometria cuidadosa do"),
        (315, 250, "espaço em branco no centro da folha"),
        (315, 265, "permitiu que cada coluna fosse lida"),
        (315, 280, "na ordem exata imaginada pelo autor"),
        (315, 295, "antes de se transformar em livro digital."),
    ]
    for x, y, text in left_col + right_col:
        p2.insert_text((x, y), text, fontsize=10.5, fontname="tiro")

    p2.insert_text((285, 805), "- 2 -", fontsize=9.0, fontname="helv")

    doc.save(str(out))
    doc.close()
    return out
