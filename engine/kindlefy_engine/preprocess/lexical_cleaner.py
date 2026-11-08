from __future__ import annotations

import re
import unicodedata
from typing import Tuple

from kindlefy_engine.models import AmbiguityFlag, CorruptedSpan, HarnessAuditEntry, RawBlock

LIGATURE_MAP = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "ft",
    "\ufb06": "st",
    "\u00ad": "",  # soft hyphen
    "\u200b": "",  # zero-width space
    "\ufeff": "",  # BOM
}

MOJIBAKE_MAP = {
    "Ã£": "ã",
    "Ã§": "ç",
    "Ã©": "é",
    "Ãª": "ê",
    "Ã³": "ó",
    "Ã´": "ô",
    "Ãµ": "õ",
    "Ãº": "ú",
    "Ã¡": "á",
    "Ã¢": "â",
    "Ã ": "à",
    "Ã­": "í",
    "Ã‰": "É",
    "Ã‡": "Ç",
    "Ãƒ": "Ã",
    "Ã“": "Ó",
    "Ãš": "Ú",
    "â€”": "—",
    "â€“": "–",
    "â€œ": "“",
    "â€\x9d": "”",
    "â€™": "’",
    "â€˜": "‘",
    "â€¦": "…",
}

OCR_COMMON_FIXES = [
    (re.compile(r"\bc~ao\b", re.IGNORECASE), "ção"),
    (re.compile(r"([a-zA-Z])c~ao\b"), r"\1ção"),
    (re.compile(r"([a-zA-Z])c~oes\b"), r"\1ções"),
    (re.compile(r"\bn~ao\b"), "não"),
    (re.compile(r"\bN~ao\b"), "Não"),
    (re.compile(r"\bs~ao\b"), "são"),
    (re.compile(r"\bpara\s+o\s+mesrno\b"), "para o mesmo"),
    (re.compile(r"\bco1no\b"), "como"),
    (re.compile(r"\bmui1o\b"), "muito"),
    (re.compile(r"\bpa1avra\b"), "palavra"),
    (re.compile(r"\bcapi1ulo\b", re.IGNORECASE), "capítulo"),
    # Frequent OCR misrecognitions in Portuguese scanned texts
    (re.compile(r"\b(?:dretores|diretores\s+eoxtoras)\b", re.IGNORECASE), "DIRETORES EDITORIAIS"),
    (re.compile(r"\bcoordenacao\s+eotoral\b", re.IGNORECASE), "COORDENAÇÃO EDITORIAL"),
    (re.compile(r"\bedicaobrasileirapublicadaporprevioacordocom\b", re.IGNORECASE), "Edição brasileira publicada por prévio acordo com"),
    (re.compile(r"\bcscravidao\b", re.IGNORECASE), "escravidão"),
    (re.compile(r"\bescravidao\b", re.IGNORECASE), "escravidão"),
    (re.compile(r"\bposicocs\b", re.IGNORECASE), "posições"),
    (re.compile(r"\brcnascimento\b", re.IGNORECASE), "renascimento"),
    (re.compile(r"\bgemco\b", re.IGNORECASE), "gêmeo"),
    (re.compile(r"\brevolucao\b", re.IGNORECASE), "revolução"),
    (re.compile(r"\brevelacao\b", re.IGNORECASE), "revelação"),
    (re.compile(r"\bliberalismo\?-", re.IGNORECASE), "liberalismo? - "),
    (re.compile(r"\bbrevepremissametodologica-", re.IGNORECASE), "breve premissa metodológica - "),
    (re.compile(r"\bremocaodoparadoxodoliberalismo\b", re.IGNORECASE), "remoção do paradoxo do liberalismo"),
    (re.compile(r"\bedicao\b", re.IGNORECASE), "edição"),
    (re.compile(r"\btraducao\b", re.IGNORECASE), "tradução"),
    (re.compile(r"\bsumario\b", re.IGNORECASE), "Sumário"),
    # Frequent Portuguese OCR letter-shape confusions (c <-> e, etc.)
    (re.compile(r"\bsc\b"), "se"),
    (re.compile(r"\bSc\b"), "Se"),
    (re.compile(r"\bdc\b"), "de"),
    (re.compile(r"\bquc\b"), "que"),
    (re.compile(r"\bparcce\b"), "parece"),
    (re.compile(r"\bbrasilciro\b"), "brasileiro"),
    (re.compile(r"\bbrasilciros\b"), "brasileiros"),
    (re.compile(r"\bbrasilcira\b"), "brasileira"),
    (re.compile(r"\bbrasilciras\b"), "brasileiras"),
    (re.compile(r"\breconhecc\b"), "reconhece"),
    (re.compile(r"\baccitá-la\b"), "aceitá-la"),
    (re.compile(r"\baccit"), "aceit"),
    (re.compile(r"\bclcs\b"), "eles"),
    (re.compile(r"\bcle\b"), "ele"),
    (re.compile(r"\blcii\b"), "lei"),
    (re.compile(r"\blcis\b"), "leis"),
    (re.compile(r"\bintrumen"), "instrumen"),
    (re.compile(r"\bpro-\s*to-liberal\b", re.IGNORECASE), "proto-liberal"),
    (re.compile(r"\bproto-\s*liberal\b", re.IGNORECASE), "proto-liberal"),
    # User-reported OCR corruptions in Losurdo and Brazilian scans
    (re.compile(r"\bpaecem\b", re.IGNORECASE), "parecem"),
    (re.compile(r"\bceebram\b", re.IGNORECASE), "celebram"),
    (re.compile(r"\bcquil[íi]brio\b", re.IGNORECASE), "equilíbrio"),
    (re.compile(r"\bmctade\b", re.IGNORECASE), "metade"),
    (re.compile(r"\bconcentro\s+de\b", re.IGNORECASE), "conceito de"),
    (re.compile(r"\bPainc\b"), "Paine"),
    (re.compile(r"\bopusculo\b", re.IGNORECASE), "opúsculo"),
    (re.compile(r'inclinada\s+à\s+prevarica[çc][ãa]o\s*"\s*(?:lo|10)\b', re.IGNORECASE), 'inclinada à prevaricação"'),
    (re.compile(r'governos"\s*em\s*"escravos\b', re.IGNORECASE), 'governos" em "escravos'),
    (re.compile(r"\bplebcu\b", re.IGNORECASE), "plebeu"),
    (re.compile(r"\bpro-priet[áa]ri", re.IGNORECASE), "proprietári"),
    (re.compile(r"\bde\s+ato\b", re.IGNORECASE), "de fato"),
    (re.compile(r"\bsp[íi]rito\b", re.IGNORECASE), "espírito"),
    (re.compile(r"\bom\s+um\b", re.IGNORECASE), "com um"),
    (re.compile(r"\bpelo\s+eu\s+car[áa]ter\b", re.IGNORECASE), "pelo seu caráter"),
    (re.compile(r"\bcnraizar", re.IGNORECASE), "enraizar"),
    (re.compile(r"\bCommon\s+Sense\s+as\s+Paine\b", re.IGNORECASE), "Common Sense de Paine"),
    (re.compile(r"\bLocke\.\s*;\s*ele\b", re.IGNORECASE), "Locke; ele"),
    # French manuscript / cursive OCR repairs (Nadja / André Breton correspondence)
    (re.compile(r"\bKncphen\b", re.IGNORECASE), "Knephen"),
    (re.compile(r"\bKn[ce]ph[ce]n\b", re.IGNORECASE), "Knephen"),
    (re.compile(r"\bAndr[ce]\s+Br[ce]ton\b", re.IGNORECASE), "André Breton"),
    (re.compile(r"\bL[ce]ona\s+D[ce]lcourt\b", re.IGNORECASE), "Léona Delcourt"),
    (re.compile(r"\bc\s*'\s*est\b"), "c'est"),
    (re.compile(r"\bC\s*'\s*est\b"), "C'est"),
    (re.compile(r"\bj\s*'\s*ai\b"), "j'ai"),
    (re.compile(r"\bJ\s*'\s*ai\b"), "J'ai"),
    (re.compile(r"\bn\s*'\s*est\b"), "n'est"),
    (re.compile(r"\bd\s*'\s*un\b"), "d'un"),
    (re.compile(r"\bd\s*'\s*une\b"), "d'une"),
    (re.compile(r"\bl\s*'\s*amour\b"), "l'amour"),
    (re.compile(r"\bl\s*'\s*âme\b"), "l'âme"),
    (re.compile(r"\bcœ\s*ur\b", re.IGNORECASE), "cœur"),
    (re.compile(r"\bcoe\s*ur\b", re.IGNORECASE), "cœur"),
]

# Portuguese enclitic pronouns and known compound prefixes that KEEP their hyphen
ENCLITIC_SUFFIXES = {
    "me", "te", "se", "lhe", "lhes", "nos", "vos",
    "o", "a", "os", "as", "lo", "la", "los", "las",
    "no", "na", "nos", "nas", "ei", "ia", "iam",
}

COMPOUND_PREFIXES = {
    "auto", "anti", "contra", "extra", "infra", "inter", "intra",
    "macro", "micro", "mini", "multi", "neo", "proto", "pseudo",
    "recém", "recem", "semi", "sobre", "sub", "super", "supra",
    "ultra", "vice", "ex", "pós", "pos", "pré", "pró",
    "bem", "mal", "além", "alem", "aquém", "aquem", "sem", "grão",
    "guarda", "porta", "puxa", "quebra", "arranha", "beija", "couve",
    "segunda", "terça", "quarta", "quinta", "sexta", "mão", "obra",
    "matéria", "materia", "meio", "curto", "longo", "alto", "baixo",
}

SUSPICIOUS_OCR_PATTERN = re.compile(
    r"\b(?=[A-Za-zÀ-ÿ01|!~^`]*[A-Za-zÀ-ÿ])(?=[A-Za-zÀ-ÿ01|!~^`]*[01|!~^`])[A-Za-zÀ-ÿ01|!~^`]{3,}\b|"
    r"(?:[\ufffd])"
)


def clean_block_lexically(
    block: RawBlock, audit_log: list[HarnessAuditEntry]
) -> RawBlock:
    """
    Repairs Unicode ligatures, UTF-8/Windows-1252 mojibake, dialogue dashes,
    and deterministic OCR glitches while flagging remaining suspicious spans
    for the Gemma 2 2B Harness.
    """
    text = block.text
    original = text

    for bad, good in LIGATURE_MAP.items():
        if bad in text:
            text = text.replace(bad, good)

    for bad, good in MOJIBAKE_MAP.items():
        if bad in text:
            text = text.replace(bad, good)

    for pattern, replacement in OCR_COMMON_FIXES:
        text = pattern.sub(replacement, text)

    # Separate glued lowercase to uppercase (e.g. "doAtlantico" -> "do Atlantico")
    text = re.sub(r"([a-zà-öø-ÿ])([A-ZÀ-ÖØ-Þ])", r"\1 \2", text)
    # Fix " c " when OCR reads " e " (conjunction) as 'c' in Portuguese
    text = re.sub(r"\b([A-Za-zÀ-ÖØ-öø-ÿ]{3,})\s+c\s+([A-Za-zÀ-ÖØ-öø-ÿ]{2,})\b", r"\1 e \2", text)

    # Normalize dialogue leading hyphen ("- Olá" -> "— Olá")
    if re.match(r"^[-–]\s+[A-ZÀ-ÖØ-Þ“\"]", text):
        text = re.sub(r"^[-–]\s+", "— ", text, count=1)

    # Strip exotic non-Portuguese diacritics / footnote superscript hallucinations (e.g. escocesasồẠạồ -> escocesas)
    text = re.sub(r"([a-zA-ZÀ-ÿ])[\u1ea0-\u1eff\u0100-\u024f\u1e00-\u1eff]+", r"\1", text)
    # Strip footnote symbol noise attached to words or quotes (e.g. brancos*®_ -> brancos, nós"* -> nós")
    text = re.sub(r'([a-zA-ZÀ-ÿ0-9\"”])[\*®_†‡]+', r"\1", text)
    # Strip leading stray punctuation (e.g. ". Isto significa que..." -> "Isto significa que...")
    text = re.sub(r"^[\.\,\;\:\'\"]\s+(?=[A-ZÀ-Ú])", "", text)
    # Strip stray asterisks before words e.g. "*cruzada" -> "cruzada", "os * governos" -> 'os "governos"'
    text = re.sub(r'^\*+\s*', '', text)
    text = re.sub(r'(?<=[\s"“])\*+\s*(?=[a-zA-ZÀ-ÿ])', '', text)
    text = re.sub(r'(?<=[a-zA-ZÀ-ÿ])\s*\*+(?=[\s"\.,;])', '', text)
    # Clean repeated corrupted quotes and OCR footnote superscripts (e.g. religião"'s -> religião", negros""" -> negros")
    text = re.sub(r'["\'”]{2,}s\b', '"', text)
    text = re.sub(r'["\'”]{2,}', '"', text)
    # Fix broken opening quote spacing e.g. "* governos absolutos" -> "governos absolutos"
    text = re.sub(r'"\s*\*\s*', '"', text)

    # Collapse multiple internal spaces (except intentional tables)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    text = unicodedata.normalize("NFC", text)

    if text != original:
        audit_log.append(
            HarnessAuditEntry(
                stage="Pass 0: Lexical & Encoding Cleaner",
                block_id=block.block_id,
                page_number=block.page_number,
                operation="LEXICAL_NORMALIZE",
                before_snippet=original[:90],
                after_snippet=text[:90],
                source="heuristic",
                accepted=True,
                reason="Reparo determinístico de ligaduras tipográficas, mojibake UTF-8 ou travessão de diálogo.",
            )
        )
        block.text = text

    if SUSPICIOUS_OCR_PATTERN.search(block.text):
        if AmbiguityFlag.OCR_ARTIFACT_SPAN not in block.ambiguity_flags:
            block.ambiguity_flags.append(AmbiguityFlag.OCR_ARTIFACT_SPAN)

    return block


def detect_corrupted_spans(block: RawBlock) -> list[CorruptedSpan]:
    """Finds specific character spans inside a block that look like OCR corruption."""
    spans: list[CorruptedSpan] = []
    for match in SUSPICIOUS_OCR_PATTERN.finditer(block.text):
        s, e = match.span()
        ctx_start = max(0, s - 35)
        ctx_end = min(len(block.text), e + 35)
        spans.append(
            CorruptedSpan(
                block_id=block.block_id,
                start_char=s,
                end_char=e,
                suspicious_text=match.group(0),
                context_window=block.text[ctx_start:ctx_end],
                reason="Caractere numérico/símbolo misturado no interior de vocábulo alfabético (provável falha de OCR).",
            )
        )
    return spans


def resolve_hyphen_split(left_word_with_hyphen: str, right_first_word: str) -> Tuple[str, bool]:
    """
    Decides whether a line-ending hyphen (`desenvol-` + `vimento` vs `guarda-` + `chuva`)
    should be joined without hyphen (`desenvolvimento`) or keep the hyphen (`guarda-chuva`).
    Returns (joined_word, was_dehyphenated).
    """
    prefix = left_word_with_hyphen.rstrip("-‐‑‒–").strip()
    suffix = right_first_word.strip()

    clean_prefix = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", prefix).lower()
    clean_suffix = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", suffix).lower()

    if not clean_prefix or not clean_suffix:
        return f"{prefix}-{suffix}", False

    # Keep hyphen for enclitic pronouns (-se, -lhe, -me, -lo, etc.)
    if clean_suffix in ENCLITIC_SUFFIXES:
        return f"{prefix}-{suffix}", False

    # Keep hyphen for compound word prefixes
    if clean_prefix in COMPOUND_PREFIXES:
        return f"{prefix}-{suffix}", False

    # Keep hyphen if the second part starts with uppercase (e.g. Anglo-Americano)
    if suffix[0].isupper():
        return f"{prefix}-{suffix}", False

    # Otherwise it is a syllable wrap caused by PDF/text line breaking -> remove hyphen!
    return f"{prefix}{suffix}", True
