"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from survey_qa import xml_parser
from survey_qa.core.models import (
    SurveyModel,
    XmlCheckbox,
    XmlRadio,
    XmlRow,
    XmlText,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def survey_model() -> SurveyModel:
    """Parse the sample survey.xml once per test session."""
    return xml_parser.parse(FIXTURES_DIR / "survey.xml")


@pytest.fixture
def s1_radio(survey_model: SurveyModel) -> XmlRadio:
    q = survey_model.by_label("S1")
    assert isinstance(q, XmlRadio)
    return q


@pytest.fixture
def s4_checkbox(survey_model: SurveyModel) -> XmlCheckbox:
    q = survey_model.by_label("S4")
    assert isinstance(q, XmlCheckbox)
    return q


# ── Doc-side fixtures (produced by the doc parser; here built by hand) ────────


def _doc_row(label: str, text: str, *, is_open: bool = False, is_exclusive: bool = False) -> XmlRow:
    return XmlRow(
        label=label,
        text=text,
        text_raw=text,
        is_open=is_open,
        is_exclusive=is_exclusive,
        id=f"doc:row:{label}",
    )


@pytest.fixture
def s4_doc() -> XmlCheckbox:
    """Doc-side representation of S4 — a checkbox."""
    return XmlCheckbox(
        label="S4",
        id="doc:S4",
        position=0,
        title="Do you currently, or have you ever, worked for the following companies or industries?",
        title_raw="Do you currently, or have you ever, worked for the following companies or industries?",
        atleast=1,
        rows=[
            _doc_row("r1", "Amazon"),
            _doc_row("r2", "Apple"),
            _doc_row("r3", "Google"),
            _doc_row("r4", "Meta/ Facebook/Instagram"),
            _doc_row("r5", "Microsoft"),
            _doc_row("r6", "TikTok"),
            _doc_row("r7", "Government"),
            _doc_row("r8", "Advertising"),
            _doc_row("r9", "An immediate family member currently works for one of the above"),
            _doc_row("r10", "None of the above", is_exclusive=True),
        ],
    )


@pytest.fixture
def s1_doc() -> XmlRadio:
    """Doc-side representation of S1 — a radio."""
    return XmlRadio(
        label="S1",
        id="doc:S1",
        position=0,
        title="Where do you live?",
        title_raw="Where do you live?",
        rows=[
            _doc_row("r1", "United States"),
            _doc_row("r2", "Canada"),
            _doc_row("r3", "United Kingdom"),
            _doc_row("r4", "Germany"),
            _doc_row("r5", "India"),
            _doc_row("r6", "Singapore"),
            _doc_row("r7", "Australia"),
            _doc_row("r8", "Other, please specify:", is_open=True),
        ],
    )


@pytest.fixture
def simple_doc_survey(s1_doc: XmlRadio) -> SurveyModel:
    return SurveyModel(survey_label="doc", elements=[s1_doc])
