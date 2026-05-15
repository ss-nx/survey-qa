"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from survey_qa import xml_parser
from survey_qa.core.models import (
    ParsedOption,
    ParsedQuestion,
    QuestionnaireModel,
    SurveyModel,
    XmlCheckbox,
    XmlRadio,
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


@pytest.fixture
def s4_questionnaire() -> ParsedQuestion:
    """Minimal questionnaire representation of S4 for check tests."""
    return ParsedQuestion(
        label="S4",
        text="Do you currently, or have you ever, worked for the following companies or industries?",
        type_hint="checkbox",
        atleast=1,
        options=[
            ParsedOption(text="Amazon"),
            ParsedOption(text="Apple"),
            ParsedOption(text="Google"),
            ParsedOption(text="Meta/ Facebook/Instagram"),
            ParsedOption(text="Microsoft"),
            ParsedOption(text="TikTok"),
            ParsedOption(text="Government"),
            ParsedOption(text="Advertising"),
            ParsedOption(text="An immediate family member currently works for one of the above"),
            ParsedOption(text="None of the above", is_exclusive=True),
        ],
    )


@pytest.fixture
def s1_questionnaire() -> ParsedQuestion:
    """Minimal questionnaire representation of S1 for check tests."""
    return ParsedQuestion(
        label="S1",
        text="Where do you live?",
        type_hint="radio",
        options=[
            ParsedOption(text="United States"),
            ParsedOption(text="Canada"),
            ParsedOption(text="United Kingdom"),
            ParsedOption(text="Germany"),
            ParsedOption(text="India"),
            ParsedOption(text="Singapore"),
            ParsedOption(text="Australia"),
            ParsedOption(text="Other, please specify:", is_open=True),
        ],
    )


@pytest.fixture
def simple_questionnaire(s1_questionnaire: ParsedQuestion) -> QuestionnaireModel:
    return QuestionnaireModel(questions=[s1_questionnaire])
