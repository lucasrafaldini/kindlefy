"""
Perfis de Contexto e Harness Segmentados por Idioma (Português, Francês, Espanhol e Inglês).

Fornece regras gramaticais, conectores sintáticos de quebra de linha, prefixos de translineação,
dicionários de reparo de OCR/diacríticos e instruções de prompt específicas por língua para o
Gemma 2 2B e o InvariantGuard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

from kindlefy_engine.models import RawBlock


@dataclass
class LanguageProfile:
    code: str  # "pt", "fr", "es", "en"
    name: str
    native_name: str
    toc_regex: Pattern[str]
    chapter_regex: Pattern[str]
    part_regex: Pattern[str]
    special_section_regex: Pattern[str]
    trailing_connectors_regex: Pattern[str]
    non_heading_particles_regex: Pattern[str]
    enclitic_suffixes: set[str] = field(default_factory=set)
    compound_prefixes: set[str] = field(default_factory=set)
    ocr_fixes: list[tuple[Pattern[str], str]] = field(default_factory=list)
    llm_system_directive: str = ""


LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "pt": LanguageProfile(
        code="pt",
        name="Português",
        native_name="Português (Brasil / Portugal)",
        toc_regex=re.compile(
            r"(?:^|\n)\s*(?:sum[áa]rio|índice|indice|tabela\s+de\s+conte[úu]do)\b",
            re.IGNORECASE,
        ),
        chapter_regex=re.compile(
            r"^(?:cap[íi]tulo|cap\.?|carta|parte)\s+(?:\d+|[ivxlcdm]+|um|dois|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez)\b",
            re.IGNORECASE,
        ),
        part_regex=re.compile(
            r"^(?:parte|livro|volume|tomo)\s+(?:\d+|[ivxlcdm]+|um|dois|tr[êe]s|quatro|primeira|segunda|terceira)\b",
            re.IGNORECASE,
        ),
        special_section_regex=re.compile(
            r"^(?:pr[óo]logo|ep[íi]logo|pref[áa]cio|introdu[çc][ãa]o|conclus[ãa]o|posf[áa]cio|agradecimentos|notas|sum[áa]rio|ap[êe]ndice|uma\s+breve\s+premissa\s+metodol[óo]gica)\s*$",
            re.IGNORECASE,
        ),
        trailing_connectors_regex=re.compile(
            r"\b(?:de|do|da|dos|das|em|no|na|nos|nas|por|para|com|sem|que|se|ou|e|um|uma|o|a|os|as|ao|aos|à|às|como|quando|entre|sobre|até|pelo|pela)\s*[,;]?$",
            re.IGNORECASE,
        ),
        non_heading_particles_regex=re.compile(
            r"\b(?:não|ele|ela|eles|elas|mas|porém|contudo|todavia|entretanto|quando|onde|como|porque|por\s+isso)\b",
            re.IGNORECASE,
        ),
        enclitic_suffixes={
            "me", "te", "se", "lhe", "lhes", "nos", "vos",
            "o", "a", "os", "as", "lo", "la", "los", "las",
            "no", "na", "nos", "nas", "ei", "ia", "iam",
        },
        compound_prefixes={
            "auto", "anti", "contra", "extra", "infra", "inter", "intra",
            "macro", "micro", "mini", "multi", "neo", "proto", "pseudo",
            "recém", "recem", "semi", "sobre", "sub", "super", "supra",
            "ultra", "vice", "ex", "pós", "pos", "pré", "pró",
            "bem", "mal", "além", "alem", "aquém", "aquem", "sem", "grão",
            "guarda", "porta", "puxa", "quebra", "arranha", "beija",
        },
        ocr_fixes=[
            (re.compile(r"\bplebcu\b", re.I), "plebeu"),
            (re.compile(r"\bpro-priet[áa]ri", re.I), "proprietári"),
            (re.compile(r"\bde\s+ato\b", re.I), "de fato"),
            (re.compile(r"\bsp[íi]rito\b", re.I), "espírito"),
            (re.compile(r"\bom\s+um\b", re.I), "com um"),
            (re.compile(r"\bpaecem\b", re.I), "parecem"),
            (re.compile(r"\bceebram\b", re.I), "celebram"),
            (re.compile(r"\bcquil[íi]brio\b", re.I), "equilíbrio"),
            (re.compile(r"\bmctade\b", re.I), "metade"),
        ],
        llm_system_directive=(
            "Idioma ativo: PORTUGUÊS. Preserve rigorosamente acentos agudos, circunflexos, til (ã, õ), "
            "cedilha (ç), crase (à) e ênclises pronominais (-se, -lo, -la)."
        ),
    ),
    "fr": LanguageProfile(
        code="fr",
        name="Francês",
        native_name="Français (Édition & Manuscrits)",
        toc_regex=re.compile(
            r"(?:^|\n)\s*(?:sommaire|table\s+des\s+mati[èe]res|index\s+des\s+lettres)\b",
            re.IGNORECASE,
        ),
        chapter_regex=re.compile(
            r"^(?:chapitre|chap\.?|lettre|planche|partie|acte)\s+(?:\d+|[ivxlcdm]+|premier|premi[èe]re|un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\b",
            re.IGNORECASE,
        ),
        part_regex=re.compile(
            r"^(?:partie|livre|tome|dossier)\s+(?:\d+|[ivxlcdm]+|premier|premi[èe]re|second|seconde|deuxi[èe]me|troisi[èe]me)\b",
            re.IGNORECASE,
        ),
        special_section_regex=re.compile(
            r"^(?:avant-propos|pr[ée]face|introduction|conclusion|postface|[ée]pilogue|prologue|notice\s+biographique|note\s+[ée]ditoriale|sommaire)\s*$",
            re.IGNORECASE,
        ),
        trailing_connectors_regex=re.compile(
            r"\b(?:de|du|des|le|la|les|un|une|dans|pour|avec|sans|sur|sous|chez|entre|vers|par|mais|ou|et|donc|or|ni|car|que|qui|dont|o[ùu]|comme|quand|lorsque|puisque)\s*[,;]?$",
            re.IGNORECASE,
        ),
        non_heading_particles_regex=re.compile(
            r"\b(?:ne|pas|plus|jamais|il|elle|ils|elles|nous|vous|mais|cependant|pourtant|lorsque|parce\s+que|comme)\b",
            re.IGNORECASE,
        ),
        enclitic_suffixes={
            "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
            "moi", "toi", "lui", "leur", "le", "la", "les", "y", "en", "ci", "là", "même", "mêmes",
        },
        compound_prefixes={
            "après", "avant", "arrière", "auto", "contre", "entre", "extra",
            "grand", "demi", "mi", "multi", "néo", "non", "outre", "เกือบ",
            "quasi", "sans", "semi", "sous", "sur", "ultra", "vice", "bien", "mal",
        },
        ocr_fixes=[
            (re.compile(r"\bKncphen\b", re.I), "Knephen"),
            (re.compile(r"\bKn[ce]ph[ce]n\b", re.I), "Knephen"),
            (re.compile(r"\bAndr[ce]\s+Br[ce]ton\b", re.I), "André Breton"),
            (re.compile(r"\bL[ce]ona\s+D[ce]lcourt\b", re.I), "Léona Delcourt"),
            (re.compile(r"\bc\s*'\s*est\b"), "c'est"),
            (re.compile(r"\bC\s*'\s*est\b"), "C'est"),
            (re.compile(r"\bj\s*'\s*ai\b"), "j'ai"),
            (re.compile(r"\bJ\s*'\s*ai\b"), "J'ai"),
            (re.compile(r"\bn\s*'\s*est\b"), "n'est"),
            (re.compile(r"\bd\s*'\s*un\b"), "d'un"),
            (re.compile(r"\bd\s*'\s*une\b"), "d'une"),
            (re.compile(r"\bl\s*'\s*amour\b"), "l'amour"),
            (re.compile(r"\bl\s*'\s*âme\b"), "l'âme"),
            (re.compile(r"\bL\s*'\s*âme\b"), "L'âme"),
            (re.compile(r"\bcœ\s*ur\b", re.I), "cœur"),
            (re.compile(r"\bcoe\s*ur\b", re.I), "cœur"),
            (re.compile(r"\bsœ\s*ur\b", re.I), "sœur"),
            (re.compile(r"\bœ\s*uvre\b", re.I), "œuvre"),
            (re.compile(r"\bv[ée]êtes\b", re.I), "vérités"),
        ],
        llm_system_directive=(
            "Langue active : FRANÇAIS. Préservez scrupuleusement les élisions (j'ai, c'est, l'âme, d'un, qu'il), "
            "les ligatures (œ dans cœur, œuvre, sœur), les accents (é, è, ê, à, ù, ç) et les formules épistolaires."
        ),
    ),
    "es": LanguageProfile(
        code="es",
        name="Espanhol",
        native_name="Español (Edición Literaria y Académica)",
        toc_regex=re.compile(
            r"(?:^|\n)\s*(?:índice|indice|tabla\s+de\s+contenidos?|sumario|contenido)\b",
            re.IGNORECASE,
        ),
        chapter_regex=re.compile(
            r"^(?:cap[íi]tulo|cap\.?|carta|parte)\s+(?:\d+|[ivxlcdm]+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|primero|segundo|tercero)\b",
            re.IGNORECASE,
        ),
        part_regex=re.compile(
            r"^(?:parte|libro|tomo|volumen)\s+(?:\d+|[ivxlcdm]+|primera|segunda|tercera|cuarta)\b",
            re.IGNORECASE,
        ),
        special_section_regex=re.compile(
            r"^(?:pr[óo]logo|ep[íi]logo|prefacio|introducci[óo]n|conclusi[óo]n|agradecimientos|notas|ap[ée]ndice|bibliograf[íi]a)\s*$",
            re.IGNORECASE,
        ),
        trailing_connectors_regex=re.compile(
            r"\b(?:de|del|la|el|los|las|un|una|unos|unas|en|por|para|con|sin|sobre|entre|hacia|hasta|desde|que|como|cuando|donde|pero|sino|mas|y|e|o|u|ni|al)\s*[,;]?$",
            re.IGNORECASE,
        ),
        non_heading_particles_regex=re.compile(
            r"\b(?:no|él|ella|ellos|ellas|pero|sin\s+embargo|aunque|cuando|donde|porque|como|también)\b",
            re.IGNORECASE,
        ),
        enclitic_suffixes=set(),  # In Spanish, enclitics are fused directly without hyphens (e.g. dándose)
        compound_prefixes={
            "anti", "auto", "contra", "ex", "extra", "infra", "inter", "intra",
            "macro", "micro", "mini", "multi", "neo", "pos", "post", "pre",
            "pro", "pseudo", "semi", "sub", "super", "supra", "tele", "ultra", "vice",
        },
        ocr_fixes=[
            (re.compile(r"\bc~i[oó]n\b", re.I), "ción"),
            (re.compile(r"\bn~a\b", re.I), "ña"),
            (re.compile(r"\bn~o\b", re.I), "ño"),
            (re.compile(r"\bqne\b"), "que"),
            (re.compile(r"\bdel\s+rnismo\b", re.I), "del mismo"),
            (re.compile(r"\btambi[eé]n\b", re.I), "también"),
        ],
        llm_system_directive=(
            "Idioma activo: ESPAÑOL. Preserve estrictamente la letra ñ, los signos de apertura (¿, ¡), "
            "las tildes diacríticas (él, tú, más, sí, qué, cómo) y la unión silábica sin guion."
        ),
    ),
    "en": LanguageProfile(
        code="en",
        name="Inglês",
        native_name="English (Academic, Forensic & Literary)",
        toc_regex=re.compile(
            r"(?:^|\n)\s*(?:table\s+of\s+contents|contents|index\s+of\s+exhibits)\b",
            re.IGNORECASE,
        ),
        chapter_regex=re.compile(
            r"^(?:chapter|chap\.?|thread|e-?mail|exhibit|letter|section)\s+(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            re.IGNORECASE,
        ),
        part_regex=re.compile(
            r"^(?:part|book|volume|dossier)\s+(?:\d+|[ivxlcdm]+|one|two|three|four|first|second|third)\b",
            re.IGNORECASE,
        ),
        special_section_regex=re.compile(
            r"^(?:prologue|epilogue|preface|foreword|introduction|conclusion|afterword|acknowledgments|appendix|references|bibliography|abstract|table\s+of\s+authorities|preliminary\s+statement|background|argument)\s*$",
            re.IGNORECASE,
        ),
        trailing_connectors_regex=re.compile(
            r"\b(?:of|the|a|an|in|on|at|to|for|with|from|by|about|as|into|like|through|after|over|between|out|against|during|without|before|under|around|among|and|or|but|that|which|who|whom|whose|when|where|while)\s*[,;]?$",
            re.IGNORECASE,
        ),
        non_heading_particles_regex=re.compile(
            r"\b(?:not|he|she|they|we|you|but|however|although|because|since|unless|whereas|would|could|should|have|has|had)\b",
            re.IGNORECASE,
        ),
        enclitic_suffixes={
            "in", "law", "up", "to", "date", "of", "the", "art", "free", "based", "aware", "like", "wise", "fold",
        },
        compound_prefixes={
            "self", "non", "anti", "co", "counter", "cross", "ex", "all", "half",
            "high", "low", "well", "ill", "mid", "multi", "neo", "over", "post",
            "pre", "pro", "quasi", "re", "semi", "sub", "super", "ultra", "under", "vice", "peer",
        },
        ocr_fixes=[
            (re.compile(r"\btbe\b"), "the"),
            (re.compile(r"\bTbe\b"), "The"),
            (re.compile(r"\bwliich\b"), "which"),
            (re.compile(r"\bwbich\b"), "which"),
            (re.compile(r"\bfi\s+rst\b"), "first"),
        ],
        llm_system_directive=(
            "Active language: ENGLISH. Preserve contractions (don't, it's, I've), email headers "
            "(From:, To:, Date:, Subject:), legal citations, and compound hyphens (peer-to-peer, self-attention)."
        ),
    ),
}


def detect_document_language(blocks: list[RawBlock], hint: str = "auto") -> LanguageProfile:
    """
    Detecta automaticamente o idioma predominante do documento (pt, fr, es, en)
    com base na distribuição de stopwords, diacríticos e marcadores estruturais,
    ou utiliza o idioma explícito se configurado pelo usuário.
    """
    if hint and hint.lower() not in {"auto", ""}:
        norm = hint.lower().split("-")[0]
        if norm in LANGUAGE_PROFILES:
            return LANGUAGE_PROFILES[norm]

    sample_text = " ".join(b.text for b in blocks[:80]).lower()
    if not sample_text.strip():
        return LANGUAGE_PROFILES["pt"]

    scores = {
        "pt": len(re.findall(r"\b(?:não|para|como|uma|dos|das|pelo|pela|também|então|são|está|capítulo|sumário)\b|[ãõç]", sample_text)),
        "fr": len(re.findall(r"\b(?:dans|pour|avec|plus|c'est|j'ai|qu'il|n'est|sont|cette|tout|bien|lettre|sommaire|DOCTEUR|PARIS|RUE|Gare)\b|[œù]", sample_text, re.I)),
        "es": len(re.findall(r"\b(?:para|como|una|los|las|del|por|pero|también|está|son|entre|capítulo|índice|según)\b|[ñ¿¡]", sample_text)),
        "en": len(re.findall(r"\b(?:the|and|that|with|from|this|have|which|their|would|about|there|between|subject|thread)\b", sample_text)),
    }

    best_lang = max(scores, key=lambda k: scores[k])
    if scores[best_lang] == 0:
        return LANGUAGE_PROFILES["pt"]
    return LANGUAGE_PROFILES[best_lang]
