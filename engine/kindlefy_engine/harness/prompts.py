from __future__ import annotations

from kindlefy_engine.models import CorruptedSpan, RawBlock


def format_gemma2_chat(system_and_user_prompt: str) -> str:
    """
    Formats a prompt using Gemma 2's official instruction template.
    """
    return (
        "<start_of_turn>user\n"
        f"{system_and_user_prompt.strip()}\n"
        "<end_of_turn>\n"
        "<start_of_turn>model\n"
    )


def build_pass1_heading_prompt(
    candidate_blocks: list[tuple[RawBlock, str, str]], body_font_size: float
) -> str:
    """
    Builds Pass 1 prompt for Gemma 2 2B: Structural Hierarchy & Heading Classification.
    Each item is (block, prev_context, next_context).
    """
    items_str = []
    for blk, prev_ctx, next_ctx in candidate_blocks:
        ratio = round(blk.font_size / max(1.0, body_font_size), 2)
        items_str.append(
            f"- ID={blk.block_id} | page={blk.page_number} | size_ratio={ratio}x "
            f"| bold={blk.is_bold} | italic={blk.is_italic} | all_caps={blk.is_all_caps} "
            f"| space_before={blk.space_before}pt\n"
            f"  PREV: \"{prev_ctx[:80]}\"\n"
            f"  TEXT: \"{blk.text[:120]}\"\n"
            f"  NEXT: \"{next_ctx[:80]}\""
        )

    joined = "\n".join(items_str)
    prompt = f"""Você é o motor de diagramação editorial Kindlefy (Gemma 2 2B Harness).
Sua tarefa é classificar blocos estruturais ambíguos extraídos de um documento ou PDF para montar um livro Kindle (EPUB 3 / MOBI) perfeito.

REGRAS ESTRITAS:
1. NUNCA reescreva o texto do autor. Apenas classifique o papel (`role`) de cada bloco listado.
2. Use `part_title` para divisões maiores (ex: "PARTE I", "LIVRO DOIS").
3. Use `chapter_title` para inícios de capítulo (ex: "Capítulo 1", "I", "Prólogo", ou títulos destacados em fonte maior/negrito no topo de seção).
4. Se o bloco logo a seguir (`NEXT`) for o subtítulo imediato do capítulo (ex: "Capítulo 1" seguido de "A Chegada"), marque `merge_subtitle_next: true`.
5. Se for cabeçalho de página vazado no meio do texto (ex: título do livro ou autor repetido isoladamente), classifique como `running_header`.
6. Se for citação curta em itálico logo após o título do capítulo, classifique como `epigraph`.

BLOCOS CANDIDATOS (Fonte base do corpo = {body_font_size}pt):
{joined}

Responda APENAS com o JSON estrito seguindo a gramática GBNF."""
    return format_gemma2_chat(prompt)


def build_pass2_boundary_prompt(
    boundary_pairs: list[tuple[RawBlock, RawBlock]]
) -> str:
    """
    Builds Pass 2 prompt for Gemma 2 2B: Page-Boundary & Hard-Wrap Reflow Stitcher.
    """
    pairs_str = []
    for left, right in boundary_pairs:
        page_cross = left.page_number != right.page_number
        pairs_str.append(
            f"- PAIR ({left.block_id} -> {right.block_id}) | page_crossing={page_cross} "
            f"| right_indent={right.indent_left}pt | space_between={right.space_before}pt\n"
            f"  LEFT_END:  \"...{left.text[-75:]}\"\n"
            f"  RIGHT_START: \"{right.text[:75]}...\""
        )

    joined = "\n".join(pairs_str)
    prompt = f"""Você é o revisor de fluxo de parágrafos e paginação de PDF do Kindlefy (Gemma 2 2B Harness).
Ao converter PDFs para Kindle, frases contínuas frequentemente quebram no meio da linha ou na virada de página.

REGRAS ESTRITAS:
1. `DEHYPHENATE_JOIN`: Use quando `LEFT_END` termina com hífen de translineação silábica (ex: "desenvol-" + "vimento" -> "desenvolvimento").
2. `KEEP_HYPHEN_JOIN`: Use quando `LEFT_END` termina com hífen de palavra composta ou pronome enclítico (ex: "guarda-" + "chuva" -> "guarda-chuva", "disse-" + "lhe" -> "disse-lhe").
3. `MERGE_SPACE`: Use quando `LEFT_END` não encerrou a oração (sem ponto final, termina em preposição/artigo/vírgula ou `RIGHT_START` começa com letra minúscula continuando a sintaxe).
4. `DIALOGUE_TURN`: Use quando `RIGHT_START` inicia fala de personagem com travessão (`—`) ou aspas de novo interlocutor.
5. `KEEP_SEPARATE`: Use quando `LEFT_END` conclui um parágrafo completo e `RIGHT_START` inicia um novo parágrafo.

FRONTEIRAS PARA ANÁLISE:
{joined}

Responda APENAS com o JSON estrito seguindo a gramática GBNF."""
    return format_gemma2_chat(prompt)


def build_pass3_ocr_surgeon_prompt(spans: list[CorruptedSpan]) -> str:
    """
    Builds Pass 3 prompt for Gemma 2 2B: Micro-Span OCR & Mojibake Surgeon.
    """
    spans_str = []
    for sp in spans:
        spans_str.append(
            f"- ID={sp.block_id} | SPAN=\"{sp.suspicious_text}\" | CONTEXT=\"...{sp.context_window}...\""
        )
    joined = "\n".join(spans_str)
    prompt = f"""Você é o cirurgião ortográfico de OCR do Kindlefy (Gemma 2 2B Harness).
Abaixo estão pequenos trechos (`suspicious_span`) com prováveis erros de escaneamento/OCR (ex: números `0`, `1` ou símbolos `~`, `|` trocados por letras dentro de uma palavra).

REGRAS DE SEGURANÇA (INVARIANT GUARD):
1. Corrija SOMENTE a palavra corrompida em `repaired_span`.
2. NUNCA altere o estilo do autor, nunca adicione palavras extras e nunca reescreva a frase ao redor.
3. Se a palavra for um código ou sigla válida (ex: "MP3", "H2O", "COVID-19", "B2B"), mantenha `repaired_span` idêntico a `suspicious_span`.

TRECHOS SUSPEITOS:
{joined}

Responda APENAS com o JSON estrito seguindo a gramática GBNF."""
    return format_gemma2_chat(prompt)


def build_pass4_qa_prompt(chapter_summaries: list[dict]) -> str:
    """
    Builds Pass 4 prompt for Gemma 2 2B: Final Editorial & Pagination QA Auditor.
    """
    summary_lines = [
        f"- Cap {c['number']}: \"{c['title']}\" ({c['paragraphs']} parágrafos, {c['words']} palavras)"
        for c in chapter_summaries
    ]
    joined = "\n".join(summary_lines)
    prompt = f"""Você é o auditor final de qualidade editorial Kindlefy (Gemma 2 2B Harness).
Revise a estrutura final dos capítulos abaixo para exportação em EPUB 3 e Kindle MOBI:

ESTRUTURA DE CAPÍTULOS:
{joined}

Avalie a consistência do sumário (TOC), capitulares (drop caps no primeiro parágrafo de cada capítulo) e retorne a nota editorial e recomendações em JSON."""
    return format_gemma2_chat(prompt)
