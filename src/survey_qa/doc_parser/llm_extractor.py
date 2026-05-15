"""LLM-based structured extraction of questionnaire questions.

Stage 2 of the two-stage pipeline. Receives batches of text chunks and
returns structured ParsedQuestion objects via instructor + litellm.

Caching
-------
Results are cached on disk (diskcache) keyed by SHA-256 of the full document
text and the model name. Re-running on the same file costs nothing.

Cost estimate
-------------
A 50-question survey (~8 000 tokens) processed with gpt-4o-mini:
  ~$0.005 total.  A warm cache hit costs $0.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import diskcache
import instructor
import litellm
from pydantic import BaseModel, Field

from ..core.models import ParsedOption, ParsedQuestion
from .chunker import TextChunk, batch_chunks, split_into_chunks
from .config import LLMConfig, load_config

log = logging.getLogger(__name__)

# ── Instructor client (lazily initialised) ────────────────────────────────────

_client: instructor.Instructor | None = None


def _get_client() -> instructor.Instructor:
    global _client
    if _client is None:
        _client = instructor.from_litellm(litellm.completion)
    return _client


# ── LLM response wrapper ──────────────────────────────────────────────────────


class _ExtractionResult(BaseModel):
    """Wrapper so instructor can return a list of questions reliably."""

    questions: list[ParsedQuestion] = Field(
        description="All questions found in this text excerpt, in document order."
    )


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a survey programming assistant. Your task is to parse client questionnaire \
documents (market research surveys) and extract each question into a structured format.

Rules
-----
- Extract EVERY question you see, even if the text is partial.
- label: the question code exactly as it appears in the document (e.g. "Q1", "S2a", "D3").
  If no code is visible, infer a sequential label like "Q1", "Q2", etc.
- text: the question stem (the wording asked of the respondent). Strip routing notes.
- type_hint: classify as one of — radio, checkbox, text, number, select, html.
    radio     → pick exactly one answer (single-select)
    checkbox  → pick one or more answers (multi-select, "select all that apply")
    text      → open-ended text response
    number    → numeric input
    select    → dropdown list
    html      → display-only text or instructions (no response collected)
- options: list the answer choices. For each option:
    code         → the numeric or letter code shown (e.g. "1", "a"), or null
    text         → the option wording
    is_exclusive → true if the option is marked "exclusive" or "none of the above"
    is_open      → true if the option has a fill-in text field ("specify:", "other:")
- routing_rules: copy any skip/display logic verbatim (e.g. "If Q1=1, skip to Q5").
- optional: true if the question is labelled "(Optional)" or similar.
- atleast: for checkbox questions, the minimum selections required if stated.
- confidence: your confidence 0.0–1.0 that you extracted this question correctly.
- source_location: quote the first few words of the question text as found in the doc.
"""


def _format_batch(chunks: list[TextChunk]) -> str:
    """Combine chunks into a single user message."""
    return "\n\n---\n\n".join(c.text for c in chunks)


# ── Public API ────────────────────────────────────────────────────────────────


def extract_questions(
    text: str,
    config: LLMConfig | None = None,
) -> list[ParsedQuestion]:
    """Extract all questions from *text* using the LLM, with caching.

    Args:
        text:   Full extracted text of the questionnaire document.
        config: LLM config. Uses load_config() if not provided.

    Returns:
        Ordered list of ParsedQuestion objects.
    """
    if config is None:
        config = load_config()

    cache_key = _cache_key(text, config.model)
    config.cache_dir.mkdir(parents=True, exist_ok=True)

    with diskcache.Cache(str(config.cache_dir)) as cache:
        if cache_key in cache:
            log.info("Cache hit for document (key=%s…)", cache_key[:12])
            return cache[cache_key]  # type: ignore[return-value]

        log.info("Cache miss — calling LLM model=%s", config.model)
        questions = _run_extraction(text, config)

        cache[cache_key] = questions
        log.info("Cached %d questions (key=%s…)", len(questions), cache_key[:12])

    return questions


def _run_extraction(text: str, config: LLMConfig) -> list[ParsedQuestion]:
    """Split text into batches and call the LLM for each."""
    chunks = split_into_chunks(text)
    batches = batch_chunks(chunks)

    log.info("Processing %d chunk(s) in %d batch(es)", len(chunks), len(batches))

    client = _get_client()
    all_questions: list[ParsedQuestion] = []

    for batch_idx, batch in enumerate(batches, start=1):
        log.debug("Batch %d/%d (%d chunks)", batch_idx, len(batches), len(batch))
        result = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _format_batch(batch)},
            ],
            response_model=_ExtractionResult,
            max_retries=config.max_retries,
        )
        all_questions.extend(result.questions)

    return all_questions


def _cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(text.encode()).hexdigest()
    return f"qa:doc:{model}:{digest}"
