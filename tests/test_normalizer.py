"""Tests for the label normalizer."""

from __future__ import annotations

from survey_qa.core.models import ParsedQuestion, QuestionnaireModel
from survey_qa.doc_parser.normalizer import normalize_labels


def _qm(*labels: str) -> QuestionnaireModel:
    return QuestionnaireModel(
        questions=[ParsedQuestion(label=lbl, text=f"Question {lbl}") for lbl in labels]
    )


def _xml_labels(*labels: str) -> set[str]:
    return set(labels)


# ── Exact match ───────────────────────────────────────────────────────────────


def test_exact_match_no_warnings():
    result = normalize_labels(_xml_labels("Q1", "Q2"), _qm("Q1", "Q2"))
    assert result.matched == {"Q1": "Q1", "Q2": "Q2"}
    assert result.warnings == []
    assert result.unmatched == []


def test_exact_match_preserves_labels():
    result = normalize_labels(_xml_labels("S1"), _qm("S1"))
    q = result.aligned_model.questions[0]
    assert q.label == "S1"


# ── Case-insensitive ──────────────────────────────────────────────────────────


def test_case_insensitive_match():
    result = normalize_labels(_xml_labels("Q1"), _qm("q1"))
    assert result.matched["q1"] == "Q1"
    assert any("Case-insensitive" in w for w in result.warnings)


def test_case_insensitive_label_replaced():
    result = normalize_labels(_xml_labels("Q1"), _qm("q1"))
    assert result.aligned_model.questions[0].label == "Q1"


# ── Prefix strip ──────────────────────────────────────────────────────────────


def test_prefix_strip_match():
    result = normalize_labels(_xml_labels("Q1"), _qm("question_Q1"))
    assert result.matched["question_Q1"] == "Q1"
    assert any("Prefix" in w for w in result.warnings)


# ── Suffix match ──────────────────────────────────────────────────────────────


def test_suffix_match():
    result = normalize_labels(_xml_labels("Awareness_Q1"), _qm("Q1"))
    assert result.matched["Q1"] == "Awareness_Q1"
    assert any("Suffix" in w for w in result.warnings)


# ── Fuzzy match ───────────────────────────────────────────────────────────────


def test_fuzzy_match_above_threshold():
    # "Q01" vs "Q1" — very similar
    result = normalize_labels(_xml_labels("Q1"), _qm("Q01"), fuzzy_threshold=70.0)
    assert result.matched.get("Q01") == "Q1"
    assert any("Fuzzy" in w for w in result.warnings)


def test_fuzzy_no_match_below_threshold():
    result = normalize_labels(_xml_labels("Satisfaction"), _qm("Demographics"), fuzzy_threshold=90.0)
    assert "Demographics" in result.unmatched


# ── Unmatched ─────────────────────────────────────────────────────────────────


def test_unmatched_label_kept_in_model():
    result = normalize_labels(_xml_labels("Q1"), _qm("NOMATCH_XYZ"), fuzzy_threshold=95.0)
    assert "NOMATCH_XYZ" in result.unmatched
    assert result.aligned_model.questions[0].label == "NOMATCH_XYZ"


def test_partial_match():
    result = normalize_labels(_xml_labels("Q1", "Q2"), _qm("Q1", "UNKNOWN"))
    assert "Q1" in result.matched
    assert "UNKNOWN" in result.unmatched


# ── Mixed bag ─────────────────────────────────────────────────────────────────


def test_mixed_strategies():
    xml = _xml_labels("S1", "Awareness_Q1", "Q3")
    qm = _qm("s1", "Q1", "Q3")
    result = normalize_labels(xml, qm)

    labels = {q.label for q in result.aligned_model.questions}
    assert "S1" in labels        # case-insensitive
    assert "Awareness_Q1" in labels  # suffix
    assert "Q3" in labels        # exact
    assert result.unmatched == []
