"""Tests for the FastAPI endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from survey_qa.api.main import app
from survey_qa.core.models import (
    SurveyModel,
    XmlCheckbox,
    XmlElement,
    XmlRadio,
    XmlSelect,
    XmlText,
)

client = TestClient(app)

FIXTURE_XML = Path(__file__).parent / "fixtures" / "survey.xml"


# ── /health ───────────────────────────────────────────────────────────────────


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── POST /qa/xml ──────────────────────────────────────────────────────────────


def test_qa_xml_returns_survey_summary():
    with FIXTURE_XML.open("rb") as f:
        response = client.post("/qa/xml", files={"xml_file": ("survey.xml", f, "application/xml")})

    assert response.status_code == 200
    body = response.json()
    assert "survey_label" in body
    assert "question_count" in body
    assert "questions" in body
    assert body["question_count"] > 0


def test_qa_xml_question_fields():
    with FIXTURE_XML.open("rb") as f:
        response = client.post("/qa/xml", files={"xml_file": ("survey.xml", f, "application/xml")})

    question = response.json()["questions"][0]
    assert "label" in question
    assert "type" in question
    assert "title" in question
    assert "position" in question


def test_qa_xml_bad_file_returns_422():
    response = client.post(
        "/qa/xml",
        files={"xml_file": ("bad.xml", b"this is not xml", "application/xml")},
    )
    assert response.status_code == 422


# ── POST /qa/compare ──────────────────────────────────────────────────────────


def _xml_to_doc_side(q) -> XmlElement:
    """Build a minimal doc-side element matching the XML question's tag/label."""
    base = dict(
        label=q.label,
        id=f"doc:{q.label}",
        position=q.position,
        title=q.title,
        title_raw=q.title,
    )
    if isinstance(q, XmlCheckbox):
        return XmlCheckbox(**base, atleast=q.atleast)
    if isinstance(q, XmlText):
        return XmlText(**base)
    if isinstance(q, XmlSelect):
        return XmlSelect(**base)
    return XmlRadio(**base)


def _stub_doc_survey() -> SurveyModel:
    """A doc-side survey that matches the first few XML questions by label."""
    from survey_qa.xml_parser import parse
    survey = parse(FIXTURE_XML)
    elements: list[XmlElement] = [_xml_to_doc_side(q) for q in survey.questions()[:5]]
    return SurveyModel(survey_label="doc", elements=elements)


@patch("survey_qa.api.routes.qa.QuestionnaireParser")
def test_qa_compare_returns_findings_list(mock_parser_cls):
    mock_instance = mock_parser_cls.for_file.return_value
    mock_instance.parse.return_value = _stub_doc_survey()

    with FIXTURE_XML.open("rb") as xml_f:
        response = client.post(
            "/qa/compare",
            files={
                "xml_file": ("survey.xml", xml_f, "application/xml"),
                "questionnaire_file": ("q.docx", b"fake docx content", "application/octet-stream"),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


@patch("survey_qa.api.routes.qa.QuestionnaireParser")
def test_qa_compare_finding_shape(mock_parser_cls):
    mock_instance = mock_parser_cls.for_file.return_value
    mock_instance.parse.return_value = _stub_doc_survey()

    with FIXTURE_XML.open("rb") as xml_f:
        response = client.post(
            "/qa/compare",
            files={
                "xml_file": ("survey.xml", xml_f, "application/xml"),
                "questionnaire_file": ("q.docx", b"fake docx content", "application/octet-stream"),
            },
        )

    findings: list = response.json()
    if findings:
        f = findings[0]
        assert "check_id" in f
        assert "severity" in f
        assert "question_label" in f
        assert "message" in f


@patch("survey_qa.api.routes.qa.QuestionnaireParser")
def test_qa_compare_bad_xml_returns_422(mock_parser_cls):
    mock_instance = mock_parser_cls.for_file.return_value
    mock_instance.parse.return_value = _stub_doc_survey()

    response = client.post(
        "/qa/compare",
        files={
            "xml_file": ("bad.xml", b"not xml at all", "application/xml"),
            "questionnaire_file": ("q.docx", b"fake docx content", "application/octet-stream"),
        },
    )
    assert response.status_code == 422
