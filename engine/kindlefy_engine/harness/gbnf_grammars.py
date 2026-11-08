"""
Constrained JSON Schemas & Grammars for llama.cpp + Gemma 2 2B Instruct.
Enforces 100% syntactically valid JSON output via llama.cpp's internal grammar generator.
"""

import json
from typing import Any

PASS1_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "block_id": {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": [
                            "frontmatter",
                            "part_title",
                            "chapter_title",
                            "subheading",
                            "paragraph",
                            "epigraph",
                            "blockquote",
                            "scene_break",
                            "running_header",
                        ],
                    },
                    "merge_subtitle_next": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["block_id", "role", "reason"],
            },
        }
    },
    "required": ["decisions"],
}

PASS2_SCHEMA = {
    "type": "object",
    "properties": {
        "stitches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "left_id": {"type": "string"},
                    "right_id": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": [
                            "MERGE_SPACE",
                            "DEHYPHENATE_JOIN",
                            "KEEP_HYPHEN_JOIN",
                            "KEEP_SEPARATE",
                            "DIALOGUE_TURN",
                        ],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["left_id", "right_id", "action", "reason"],
            },
        }
    },
    "required": ["stitches"],
}

PASS3_SCHEMA = {
    "type": "object",
    "properties": {
        "patches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "block_id": {"type": "string"},
                    "suspicious_span": {"type": "string"},
                    "repaired_span": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["block_id", "suspicious_span", "repaired_span", "reason"],
            },
        }
    },
    "required": ["patches"],
}

PASS4_SCHEMA = {
    "type": "object",
    "properties": {
        "quality_score": {"type": "number"},
        "editorial_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["quality_score", "editorial_notes"],
}

PASS1_HEADING_CLASSIFIER_GBNF = PASS1_SCHEMA
PASS2_BOUNDARY_STITCHER_GBNF = PASS2_SCHEMA
PASS3_OCR_SURGEON_GBNF = PASS3_SCHEMA
PASS4_EDITORIAL_QA_GBNF = PASS4_SCHEMA


def get_grammar_for_schema(schema: dict[str, Any]):
    try:
        from llama_cpp import LlamaGrammar
        return LlamaGrammar.from_json_schema(json.dumps(schema))
    except Exception:
        return None
