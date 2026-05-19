"""LLM-based doc → compact-format extraction.

Single-pass approach
--------------------
1. Send the full extracted document text to the LLM as a plain-text completion.
2. The LLM rewrites it as compact format (~5× smaller than structured JSON).
3. compact_parser.parse_compact() deterministically converts that to SurveyModel.

If the compact parser raises, one automatic retry is attempted: the LLM is
shown its own output alongside the parse error and asked to fix it.

Caching
-------
Results are cached on disk (diskcache) keyed by SHA-256 of:
  - the full document text
  - the model name
  - the SurveyModel JSON schema hash (so model schema changes invalidate the cache)

A warm cache hit costs $0.
"""

from __future__ import annotations

import hashlib
import json
import logging

import diskcache
import litellm

from ..core.models import SurveyModel
from .compact_parser import CompactParseError, parse_compact
from .config import LLMConfig, load_config

log = logging.getLogger(__name__)


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a survey programming assistant. Convert the questionnaire document \
below into compact format. Output ONLY the compact format — no commentary, \
no markdown fences, no extra text.

== Compact format ==

One block per question, separated by a blank line:

  ## <type> [label]
  <title — one or more lines>
  <key>: <value>
  options:
    1. Option text
    2. Option text  [open]
    99. Option text  [exclusive]

Types: radio · checkbox · text · number · float · select · html · term · quota · goto

Rules
-----
- [label] in the header: include when the doc shows an explicit question code
  (e.g. Q1, S2a, D3). Omit when the doc has no code for that question.
- title: the question stem verbatim. Strip routing notes and section headers.
- options / rows / choices / cols: numbered items (N. text).
  Copy the doc's codes verbatim when shown; number 1..N sequentially when not.
- Grid question (rating matrix etc.): use both rows: and cols: lists.
- [open] tag on items with "specify ___", "Other, please specify", fill-in fields.
- [exclusive] tag on "None of the above", "Prefer not to say", similar.
- display: <text>  — any routing or display logic noted in the doc.
- flags: optional  — when the doc marks the question optional.
- atleast: N  — checkbox minimum only when explicitly stated.
- term: <coord>  — termination/screen-out (e.g. r4, r1.c5 or r2.c5).
- note: <text>  — when you are uncertain about the extraction.
- Ambiguous or display-only text → ## html block.
- Join multi-line option text into one line.
- Only emit keys that differ from the default (silence = standard).
- Inline formatting: <b>bold</b>, <i>italic</i>, <u>underline</u>. Ignore color.
"""


# ── Public API ────────────────────────────────────────────────────────────────


def extract_survey(
    text: str,
    config: LLMConfig | None = None,
) -> SurveyModel:
    """Extract a SurveyModel from document text via compact format, with caching.

    Args:
        text:   Full extracted text of the questionnaire document.
        config: LLM config. Uses load_config() if not provided.

    Returns:
        SurveyModel containing XmlElement instances, one per extracted question.
    """
    if config is None:
        config = load_config()

    cache_key = _cache_key(text, config.model)
    config.cache_dir.mkdir(parents=True, exist_ok=True)

    with diskcache.Cache(str(config.cache_dir)) as cache:
        if cache_key in cache:
            log.info("Cache hit (key=%s…)", cache_key[:12])
            return cache[cache_key]  # type: ignore[return-value]

        log.info("Cache miss — calling LLM model=%s", config.model)
        compact_text = _call_llm(text, config)
        survey = _parse_with_fallback(compact_text, config)

        cache[cache_key] = survey
        log.info("Cached %d elements (key=%s…)", len(survey.elements), cache_key[:12])

    return survey


# ── LLM calls ─────────────────────────────────────────────────────────────────


def _call_llm(text: str, config: LLMConfig) -> str:
    """Send document text to the LLM; return the compact-format string."""
    response = litellm.completion(
        model=config.model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content or ""


def _call_llm_retry(bad_compact: str, error: str, config: LLMConfig) -> str:
    """Ask the LLM to fix its own malformed compact output."""
    response = litellm.completion(
        model=config.model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "assistant", "content": bad_compact},
            {
                "role": "user",
                "content": (
                    f"The compact format above has a parse error:\n\n{error}\n\n"
                    "Fix it and output ONLY the corrected compact format."
                ),
            },
        ],
    )
    return response.choices[0].message.content or ""


def _parse_with_fallback(compact_text: str, config: LLMConfig) -> SurveyModel:
    """Parse compact text; retry once with the LLM if the parser fails."""
    try:
        return parse_compact(compact_text)
    except CompactParseError as exc:
        log.warning("Compact parse failed (%s) — retrying with error context", exc)
        fixed = _call_llm_retry(compact_text, str(exc), config)
        return parse_compact(fixed)


# ── Cache key (includes schema version) ──────────────────────────────────────


def _schema_hash() -> str:
    """Hash of the SurveyModel JSON schema. Changes invalidate the cache."""
    schema_json = json.dumps(SurveyModel.model_json_schema(), sort_keys=True)
    return hashlib.sha256(schema_json.encode()).hexdigest()[:12]


def _cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(text.encode()).hexdigest()
    return f"qa:doc:{model}:{_schema_hash()}:{digest}"
