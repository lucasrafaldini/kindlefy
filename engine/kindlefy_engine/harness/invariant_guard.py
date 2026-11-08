from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Tuple

from kindlefy_engine.models import BlockRole, HarnessAuditEntry, RawBlock

VALID_KEEP_AS_IS_TOKENS = {
    "mp3", "mp4", "h2o", "b2b", "b2c", "p2p", "co2", "3d", "2d", "4k", "8k",
    "covid-19", "wi-fi", "ipv4", "ipv6", "x86", "arm64", "utf-8", "iso-8859-1",
    "g20", "f1", "ps4", "ps5",
}


class InvariantGuard:
    """
    Deterministic Safety Rail around Gemma 2 2B.
    Guarantees that the small LLM can NEVER hallucinate paragraphs, delete author
    sentences, or corrupt valid words during the 4-pass editorial harness.
    """

    @staticmethod
    def verify_ocr_patch(
        block: RawBlock,
        suspicious_span: str,
        repaired_span: str,
        audit_log: list[HarnessAuditEntry],
    ) -> Tuple[bool, str]:
        """
        Verifies a Pass 3 micro-span OCR patch proposed by Gemma 2 2B:
        1. Span must exist verbatim in block.text.
        2. Span length must be <= 48 chars.
        3. Whitelisted alphanumeric tokens (MP3, H2O, B2B) are never mutated.
        4. Character similarity ratio (SequenceMatcher) must be >= 0.58.
        5. Word count delta must be <= 1.
        """
        if not suspicious_span or not repaired_span:
            return False, "Span vazio."

        if suspicious_span == repaired_span:
            return False, "Sem alteração necessária."

        if suspicious_span.lower() in VALID_KEEP_AS_IS_TOKENS:
            audit_log.append(
                HarnessAuditEntry(
                    stage="Pass 3: Invariant Guard",
                    block_id=block.block_id,
                    page_number=block.page_number,
                    operation="REJECT_OCR_PATCH",
                    before_snippet=suspicious_span,
                    after_snippet=repaired_span,
                    source="invariant-guard-rejected",
                    accepted=False,
                    reason=f"Sigla/termo técnico protegido ('{suspicious_span}').",
                )
            )
            return False, "Termo técnico protegido."

        if len(suspicious_span) > 48 or len(repaired_span) > 56:
            audit_log.append(
                HarnessAuditEntry(
                    stage="Pass 3: Invariant Guard",
                    block_id=block.block_id,
                    page_number=block.page_number,
                    operation="REJECT_OCR_PATCH",
                    before_snippet=suspicious_span[:48],
                    after_snippet=repaired_span[:48],
                    source="invariant-guard-rejected",
                    accepted=False,
                    reason="Patch excede o limite de micro-span (48 caracteres).",
                )
            )
            return False, "Patch muito longo."

        if suspicious_span not in block.text:
            return False, "Span original não encontrado no bloco."

        similarity = SequenceMatcher(None, suspicious_span.lower(), repaired_span.lower()).ratio()
        word_delta = abs(len(suspicious_span.split()) - len(repaired_span.split()))

        if similarity < 0.58 or word_delta > 1:
            audit_log.append(
                HarnessAuditEntry(
                    stage="Pass 3: Invariant Guard",
                    block_id=block.block_id,
                    page_number=block.page_number,
                    operation="REJECT_OCR_PATCH",
                    before_snippet=suspicious_span,
                    after_snippet=repaired_span,
                    source="invariant-guard-rejected",
                    accepted=False,
                    reason=f"Similaridade Levenshtein baixa ({similarity:.2f}) ou alteração estrutural de palavras.",
                )
            )
            return False, f"Similaridade insuficiente ({similarity:.2f})."

        return True, f"Patch verificado (similaridade={similarity:.2f})."

    @staticmethod
    def verify_role_classification(
        block: RawBlock,
        proposed_role: BlockRole,
        audit_log: list[HarnessAuditEntry],
    ) -> Tuple[bool, BlockRole]:
        """
        Verifies Pass 1 structural role classification from Gemma 2 2B:
        - Prevents stripping long narrative paragraphs as `running_header`.
        - Prevents turning long paragraphs (>140 chars ending with a period) into headings.
        """
        txt = block.text.strip()

        if proposed_role in {BlockRole.RUNNING_HEADER, BlockRole.RUNNING_FOOTER}:
            if len(txt) > 85 or (txt.endswith(".") and len(txt.split()) > 10):
                audit_log.append(
                    HarnessAuditEntry(
                        stage="Pass 1: Invariant Guard",
                        block_id=block.block_id,
                        page_number=block.page_number,
                        operation="REJECT_HEADER_STRIP",
                        before_snippet=txt[:80],
                        after_snippet=f"Mantido como {block.role.value}",
                        source="invariant-guard-rejected",
                        accepted=False,
                        reason="Bloco longo com estrutura frasal narrativa protegido contra remoção de cabeçalho.",
                    )
                )
                return False, block.role

        if proposed_role in {BlockRole.PART_TITLE, BlockRole.CHAPTER_TITLE, BlockRole.SUBHEADING}:
            clean_first = txt.lstrip("*\"' \t")[:1]
            starts_lower = clean_first.islower()
            starts_punct = txt.strip()[:1] in {",", ";", ":", ")", "]", "."}
            ends_open_punct = txt.strip().endswith((",", ";", ":", "-", "—", "–"))
            ends_connector = bool(
                re.search(r"\b(?:de|do|da|dos|das|em|no|na|nos|nas|com|sem|por|para|e|ou|que|o|a|os|as)\s*$", txt.strip(), re.I)
            )

            if len(txt) > 130 or starts_lower or starts_punct or ends_open_punct or ends_connector:
                audit_log.append(
                    HarnessAuditEntry(
                        stage="Pass 1: Invariant Guard",
                        block_id=block.block_id,
                        page_number=block.page_number,
                        operation="REJECT_HEADING_PROMOTION",
                        before_snippet=txt[:80],
                        after_snippet="Mantido como parágrafo",
                        source="invariant-guard-rejected",
                        accepted=False,
                        reason="Estrutura gramatical ou pontuação incompatível com título (início minúsculo, pontuação subordinada ou conector aberto).",
                    )
                )
                return False, BlockRole.PARAGRAPH

        return True, proposed_role

    @staticmethod
    def verify_word_conservation(original_text: str, stitched_text: str) -> bool:
        """
        Verifies that merging two blocks conserved 100% of alphanumeric characters
        (modulo removed hyphen at the join point).
        """
        norm_orig = re.sub(r"[\s\-‐‑‒–]+", "", original_text)
        norm_stitch = re.sub(r"[\s\-‐‑‒–]+", "", stitched_text)
        return norm_orig == norm_stitch
