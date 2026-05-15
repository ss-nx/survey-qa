"""Tests for the label normalizer."""

from __future__ import annotations

from survey_qa.core.models import SurveyModel, XmlRadio
from survey_qa.doc_parser.normalizer import normalize_labels


def _doc(*labels: str) -> SurveyModel:
    """Build a doc-side SurveyModel with one XmlRadio per label."""
    elements = [
        XmlRadio(
            label=lbl,
            id=f"doc:{lbl}",
            position=i,
            title=f"Question {lbl}",
            title_raw=f"Question {lbl}",
            rows=[],
        )
        for i, lbl in enumerate(labels)
    ]
    return SurveyModel(survey_label="doc", elements=elements)


def _xml(*labels: str) -> SurveyModel:
    """Build an XML-side SurveyModel with one XmlRadio per label."""
    return _doc(*labels)


# ── Exact match ───────────────────────────────────────────────────────────────


def test_exact_match_no_warnings():
    result = normalize_labels(_xml("Q1", "Q2"), _doc("Q1", "Q2"))
    assert result.matched == {"Q1": "Q1", "Q2": "Q2"}
    assert result.warnings == []
    assert result.unmatched == []


def test_exact_match_preserves_labels():
    result = normalize_labels(_xml("S1"), _doc("S1"))
    q = result.aligned_model.elements[0]
    assert q.label == "S1"


# ── Case-insensitive ──────────────────────────────────────────────────────────


def test_case_insensitive_match():
    result = normalize_labels(_xml("Q1"), _doc("q1"))
    assert result.matched["q1"] == "Q1"
    assert any("Case-insensitive" in w for w in result.warnings)


def test_case_insensitive_label_replaced():
    result = normalize_labels(_xml("Q1"), _doc("q1"))
    assert result.aligned_model.elements[0].label == "Q1"


# ── Prefix strip ──────────────────────────────────────────────────────────────


def test_prefix_strip_match():
    result = normalize_labels(_xml("Q1"), _doc("question_Q1"))
    assert result.matched["question_Q1"] == "Q1"
    assert any("Prefix" in w for w in result.warnings)


# ── Suffix match ──────────────────────────────────────────────────────────────


def test_suffix_match():
    result = normalize_labels(_xml("Awareness_Q1"), _doc("Q1"))
    assert result.matched["Q1"] == "Awareness_Q1"
    assert any("Suffix" in w for w in result.warnings)


# ── Fuzzy match ───────────────────────────────────────────────────────────────


def test_fuzzy_match_above_threshold():
    # "Q01" vs "Q1" — very similar
    result = normalize_labels(_xml("Q1"), _doc("Q01"), fuzzy_threshold=70.0)
    assert result.matched.get("Q01") == "Q1"
    assert any("Fuzzy" in w for w in result.warnings)


def test_fuzzy_no_match_below_threshold():
    result = normalize_labels(
        _xml("Satisfaction"), _doc("Demographics"), fuzzy_threshold=90.0
    )
    assert "Demographics" in result.unmatched


# ── Unmatched ─────────────────────────────────────────────────────────────────


def test_unmatched_label_kept_in_model():
    result = normalize_labels(_xml("Q1"), _doc("NOMATCH_XYZ"), fuzzy_threshold=95.0)
    assert "NOMATCH_XYZ" in result.unmatched
    assert result.aligned_model.elements[0].label == "NOMATCH_XYZ"


def test_partial_match():
    result = normalize_labels(_xml("Q1", "Q2"), _doc("Q1", "UNKNOWN"))
    assert "Q1" in result.matched
    assert "UNKNOWN" in result.unmatched


# ── Mixed bag ─────────────────────────────────────────────────────────────────


def test_mixed_strategies():
    xml = _xml("S1", "Awareness_Q1", "Q3")
    doc = _doc("s1", "Q1", "Q3")
    result = normalize_labels(xml, doc)

    labels = {e.label for e in result.aligned_model.elements}
    assert "S1" in labels          # case-insensitive
    assert "Awareness_Q1" in labels  # suffix
    assert "Q3" in labels          # exact
    assert result.unmatched == []
