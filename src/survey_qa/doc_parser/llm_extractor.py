"""LLM-based structured extraction of questionnaire questions.

Stage 2 of the two-stage pipeline. Receives a document's full text, splits
it into batches, calls instructor + litellm to extract a loosely-typed
intermediate representation, then converts that into the unified `SurveyModel`
populated with `XmlElement` instances (the same types the XML parser produces).

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
from typing import Iterable

import diskcache
import instructor
import litellm
from pydantic import BaseModel, Field

from ..core.models import (
    ParserMeta,
    SurveyModel,
    XmlCheckbox,
    XmlChoice,
    XmlElement,
    XmlFloat,
    XmlHtml,
    XmlNumber,
    XmlRadio,
    XmlRow,
    XmlSelect,
    XmlText,
)
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


# ── Internal extraction shape (never leaves this module) ──────────────────────


class _ExtractedOption(BaseModel):
    """LLM's view of an answer option. Converted to XmlRow / XmlChoice."""

    code: str | None = None
    text: str
    is_exclusive: bool = False
    is_open: bool = False


class _ExtractedQuestion(BaseModel):
    """LLM's view of a question. Converted to an XmlElement before returning."""

    label: str
    text: str
    type_hint: str = "radio"  # radio | checkbox | text | number | select | html | float
    options: list[_ExtractedOption] = Field(default_factory=list)
    routing_rules: list[str] = Field(default_factory=list)
    optional: bool = False
    atleast: int | None = None
    confidence: float = 1.0
    source_location: str = ""


class _ExtractionResult(BaseModel):
    """Wrapper so instructor can return a list of questions reliably."""

    questions: list[_ExtractedQuestion] = Field(
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
- type_hint: classify as one of — radio, checkbox, text, number, select, float, html.
    radio     → pick exactly one answer (single-select)
    checkbox  → pick one or more answers (multi-select, "select all that apply")
    text      → open-ended text response
    number    → numeric input (integer)
    float     → decimal numeric input
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


def extract_survey(
    text: str,
    config: LLMConfig | None = None,
) -> SurveyModel:
    """Extract a SurveyModel from the document text using the LLM, with caching.

    Args:
        text:   Full extracted text of the questionnaire document.
        config: LLM config. Uses load_config() if not provided.

    Returns:
        SurveyModel containing XmlElement instances (one per extracted question),
        with parser_meta populated on each.
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
        extracted = _run_extraction(text, config)
        survey = _to_survey_model(extracted)

        cache[cache_key] = survey
        log.info("Cached %d elements (key=%s…)", len(survey.elements), cache_key[:12])

    return survey


def _run_extraction(text: str, config: LLMConfig) -> list[_ExtractedQuestion]:
    """Split text into batches and call the LLM for each."""
    chunks = split_into_chunks(text)
    batches = batch_chunks(chunks)

    log.info("Processing %d chunk(s) in %d batch(es)", len(chunks), len(batches))

    client = _get_client()
    all_questions: list[_ExtractedQuestion] = []

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


# ── Conversion from internal extraction shape → unified XmlElement ────────────


def _to_survey_model(extracted: Iterable[_ExtractedQuestion]) -> SurveyModel:
    """Convert the LLM's loosely-typed extraction to the unified SurveyModel."""
    elements: list[XmlElement] = []
    for position, q in enumerate(extracted):
        elements.append(_to_xml_element(q, position))
    return SurveyModel(survey_label="doc", elements=elements)


def _to_xml_element(q: _ExtractedQuestion, position: int) -> XmlElement:
    """Map an LLM-extracted question to the matching XmlElement subtype."""
    meta = _make_meta(q)
    common = dict(
        label=q.label,
        id=f"doc:{q.label}",
        position=position,
        title=q.text,
        title_raw=q.text,
        optional=q.optional,
        parser_meta=meta,
    )

    type_hint = (q.type_hint or "radio").lower()

    if type_hint == "checkbox":
        return XmlCheckbox(
            **common,
            atleast=q.atleast if q.atleast is not None else 1,
            rows=[_to_xml_row(o, i) for i, o in enumerate(q.options)],
        )
    if type_hint == "text":
        return XmlText(**common)
    if type_hint == "number":
        return XmlNumber(**common)
    if type_hint == "float":
        return XmlFloat(**common)
    if type_hint == "select":
        return XmlSelect(
            **common,
            choices=[_to_xml_choice(o, i) for i, o in enumerate(q.options)],
        )
    if type_hint == "html":
        return XmlHtml(**common)
    # default: radio
    return XmlRadio(
        **common,
        rows=[_to_xml_row(o, i) for i, o in enumerate(q.options)],
    )


def _make_meta(q: _ExtractedQuestion) -> ParserMeta:
    raw_logic = "; ".join(q.routing_rules) if q.routing_rules else None
    return ParserMeta(
        source="doc",
        confidence=q.confidence,
        source_excerpt=q.source_location or None,
        raw_display_logic=raw_logic,
    )


def _to_xml_row(o: _ExtractedOption, index: int) -> XmlRow:
    label = o.code if o.code else f"r{index + 1}"
    value = _parse_int(o.code)
    return XmlRow(
        label=label,
        value=value,
        text=o.text,
        text_raw=o.text,
        is_exclusive=o.is_exclusive,
        is_open=o.is_open,
        id=f"doc:row:{label}:{index}",
    )


def _to_xml_choice(o: _ExtractedOption, index: int) -> XmlChoice:
    label = o.code if o.code else f"c{index + 1}"
    value = _parse_int(o.code)
    return XmlChoice(
        label=label,
        value=value,
        text=o.text,
        text_raw=o.text,
        id=f"doc:choice:{label}:{index}",
    )


def _parse_int(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


# ── Cache key (includes schema version) ──────────────────────────────────────


def _schema_hash() -> str:
    """Hash of the SurveyModel JSON schema. Changes invalidate the cache."""
    schema_json = json.dumps(SurveyModel.model_json_schema(), sort_keys=True)
    return hashlib.sha256(schema_json.encode()).hexdigest()[:12]


def _cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(text.encode()).hexdigest()
    return f"qa:doc:{model}:{_schema_hash()}:{digest}"
