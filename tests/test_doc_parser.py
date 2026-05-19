"""Tests for doc_parser — extractor, chunker, and parser wiring.

LLM calls are mocked throughout; these tests never hit a real API.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from survey_qa.core.models import SurveyModel
from survey_qa.doc_parser.chunker import TextChunk, batch_chunks, split_into_chunks
from survey_qa.doc_parser.config import LLMConfig, load_config
from survey_qa.doc_parser.llm_extractor import _cache_key, extract_survey


# ── Helpers ───────────────────────────────────────────────────────────────────


def _litellm_response(content: str) -> MagicMock:
    """Build a minimal litellm completion response stub."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


_COMPACT_TWO_QUESTIONS = """\
## radio [Q1]
How often do you use our product?
options:
  1. Daily
  2. Weekly

## radio [Q2]
Please rate your satisfaction.
options:
  1. Very satisfied
  2. Satisfied
"""


# ── Config ────────────────────────────────────────────────────────────────────


def test_load_config_defaults():
    cfg = load_config()
    assert cfg.model == "gpt-4o-mini"
    assert cfg.max_retries == 3
    assert "survey_qa" in str(cfg.cache_dir)


def test_load_config_env_override(monkeypatch):
    monkeypatch.setenv("LITELLM_MODEL", "gpt-4o")
    monkeypatch.setenv("QA_LLM_RETRIES", "5")
    cfg = load_config()
    assert cfg.model == "gpt-4o"
    assert cfg.max_retries == 5


# ── Chunker ───────────────────────────────────────────────────────────────────


SAMPLE_QUESTIONNAIRE = """\
Q1. How often do you use our product?
1. Daily
2. Weekly
3. Monthly
4. Never

Q2. Please rate your satisfaction.
1. Very satisfied
2. Satisfied
3. Neutral
4. Dissatisfied

Q3. What could we improve? (Open-ended)
"""

UNSTRUCTURED_TEXT = "This is a general instructions page with no question codes."


def test_split_detects_question_boundaries():
    chunks = split_into_chunks(SAMPLE_QUESTIONNAIRE)
    assert len(chunks) == 3


def test_split_chunk_labels():
    chunks = split_into_chunks(SAMPLE_QUESTIONNAIRE)
    assert chunks[0].text.startswith("Q1.")
    assert chunks[1].text.startswith("Q2.")
    assert chunks[2].text.startswith("Q3.")


def test_split_preserves_start_line():
    chunks = split_into_chunks(SAMPLE_QUESTIONNAIRE)
    assert chunks[0].start_line == 0
    assert chunks[1].start_line > 0


def test_split_no_structure_returns_single_chunk():
    chunks = split_into_chunks(UNSTRUCTURED_TEXT)
    assert len(chunks) == 1
    assert chunks[0].text == UNSTRUCTURED_TEXT.strip()


def test_batch_chunks_single_batch_for_small_doc():
    chunks = split_into_chunks(SAMPLE_QUESTIONNAIRE)
    batches = batch_chunks(chunks)
    assert len(batches) == 1
    assert len(batches[0]) == 3


def test_batch_chunks_splits_large_doc():
    # Create chunks that exceed the per-batch limit
    big_chunk = TextChunk(text="Q" * 25_001, start_line=0)
    chunks = [big_chunk] * 3
    batches = batch_chunks(chunks)
    assert len(batches) > 1


def test_batch_chunks_never_splits_single_chunk():
    """A single oversized chunk should still appear in exactly one batch."""
    huge_chunk = TextChunk(text="Q" * 200_000, start_line=0)
    batches = batch_chunks([huge_chunk])
    assert len(batches) == 1


# ── Cache key ─────────────────────────────────────────────────────────────────


def test_cache_key_is_deterministic():
    k1 = _cache_key("hello world", "gpt-4o-mini")
    k2 = _cache_key("hello world", "gpt-4o-mini")
    assert k1 == k2


def test_cache_key_differs_for_different_text():
    k1 = _cache_key("text A", "gpt-4o-mini")
    k2 = _cache_key("text B", "gpt-4o-mini")
    assert k1 != k2


def test_cache_key_differs_for_different_model():
    k1 = _cache_key("same text", "gpt-4o-mini")
    k2 = _cache_key("same text", "gpt-4o")
    assert k1 != k2


# ── extract_survey (mocked LLM + cache) ───────────────────────────────────────


def _make_config(tmp_path: Path) -> LLMConfig:
    return LLMConfig(model="gpt-4o-mini", cache_dir=tmp_path / "cache", max_retries=1)


@patch("survey_qa.doc_parser.llm_extractor.litellm.completion")
def test_extract_survey_calls_llm_on_cache_miss(mock_completion, tmp_path):
    mock_completion.return_value = _litellm_response(_COMPACT_TWO_QUESTIONS)

    config = _make_config(tmp_path)
    result = extract_survey(SAMPLE_QUESTIONNAIRE, config)

    assert isinstance(result, SurveyModel)
    assert len(result.elements) == 2
    assert result.elements[0].label == "Q1"
    mock_completion.assert_called_once()


@patch("survey_qa.doc_parser.llm_extractor.litellm.completion")
def test_extract_survey_returns_cached_result(mock_completion, tmp_path):
    """Second call with same text must not hit the LLM."""
    mock_completion.return_value = _litellm_response(_COMPACT_TWO_QUESTIONS)

    config = _make_config(tmp_path)
    extract_survey(SAMPLE_QUESTIONNAIRE, config)  # prime the cache
    extract_survey(SAMPLE_QUESTIONNAIRE, config)  # should be served from cache

    assert mock_completion.call_count == 1


@patch("survey_qa.doc_parser.llm_extractor.litellm.completion")
def test_extract_survey_cache_miss_on_new_text(mock_completion, tmp_path):
    mock_completion.return_value = _litellm_response(_COMPACT_TWO_QUESTIONS)

    config = _make_config(tmp_path)
    extract_survey("Different text entirely.", config)
    extract_survey("Another different text.", config)

    assert mock_completion.call_count == 2


@patch("survey_qa.doc_parser.llm_extractor.litellm.completion")
def test_extract_survey_populates_parser_meta(mock_completion, tmp_path):
    """Doc parser must populate parser_meta fields from compact format."""
    compact = """\
## radio [Q1]
A question
display: If Q1=1, skip to Q5
options:
  1. Yes
  2. No
"""
    mock_completion.return_value = _litellm_response(compact)

    config = _make_config(tmp_path)
    result = extract_survey("any text", config)

    q = result.elements[0]
    assert q.parser_meta is not None
    assert q.parser_meta.source == "doc"
    assert q.parser_meta.confidence == 1.0
    assert q.parser_meta.raw_display_logic == "If Q1=1, skip to Q5"


@patch("survey_qa.doc_parser.llm_extractor.litellm.completion")
def test_extract_survey_retries_on_parse_error(mock_completion, tmp_path):
    """If the LLM returns malformed compact text, one retry is attempted."""
    # An unknown type header triggers CompactParseError in compact_parser
    bad = "## unknowntype [Q1]\nSome question text\n"
    mock_completion.side_effect = [
        _litellm_response(bad),
        _litellm_response(_COMPACT_TWO_QUESTIONS),
    ]

    config = _make_config(tmp_path)
    result = extract_survey("some doc text", config)

    assert isinstance(result, SurveyModel)
    assert mock_completion.call_count == 2


# ── DocxParser wiring (no real docx file) ────────────────────────────────────


@patch("survey_qa.doc_parser.docx_parser.extract_docx")
@patch("survey_qa.doc_parser.docx_parser.extract_survey")
def test_docx_parser_wires_extractor_and_llm(mock_extract_survey, mock_extract_docx, tmp_path):
    from survey_qa.doc_parser.docx_parser import DocxParser

    mock_extract_docx.return_value = SAMPLE_QUESTIONNAIRE
    mock_extract_survey.return_value = SurveyModel(survey_label="doc", elements=[])

    config = _make_config(tmp_path)
    parser = DocxParser(config=config)
    result = parser.parse(Path("fake.docx"))

    assert isinstance(result, SurveyModel)
    mock_extract_docx.assert_called_once_with(Path("fake.docx"))


# ── PdfParser wiring ──────────────────────────────────────────────────────────


@patch("survey_qa.doc_parser.pdf_parser.extract_pdf")
@patch("survey_qa.doc_parser.pdf_parser.extract_survey")
def test_pdf_parser_wires_extractor_and_llm(mock_extract_survey, mock_extract_pdf, tmp_path):
    from survey_qa.doc_parser.pdf_parser import PdfParser

    mock_extract_pdf.return_value = SAMPLE_QUESTIONNAIRE
    mock_extract_survey.return_value = SurveyModel(survey_label="doc", elements=[])

    config = _make_config(tmp_path)
    parser = PdfParser(config=config)
    result = parser.parse(Path("fake.pdf"))

    assert isinstance(result, SurveyModel)
    mock_extract_pdf.assert_called_once_with(Path("fake.pdf"))


# ── Factory routing ───────────────────────────────────────────────────────────


def test_factory_returns_docx_parser():
    from survey_qa.doc_parser.base import QuestionnaireParser

    parser = QuestionnaireParser.for_file(Path("survey.docx"))
    from survey_qa.doc_parser.docx_parser import DocxParser
    assert isinstance(parser, DocxParser)


def test_factory_returns_pdf_parser():
    from survey_qa.doc_parser.base import QuestionnaireParser

    parser = QuestionnaireParser.for_file(Path("survey.pdf"))
    from survey_qa.doc_parser.pdf_parser import PdfParser
    assert isinstance(parser, PdfParser)


def test_factory_raises_for_unknown_extension():
    from survey_qa.doc_parser.base import QuestionnaireParser

    with pytest.raises(ValueError, match="Unsupported"):
        QuestionnaireParser.for_file(Path("survey.xlsx"))
