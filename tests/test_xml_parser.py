"""Tests for xml_parser.parse() against the sample survey.xml fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from survey_qa import xml_parser
from survey_qa.core.models import (
    SurveyModel,
    XmlCheckbox,
    XmlGoto,
    XmlHtml,
    XmlNumber,
    XmlQuota,
    XmlRadio,
    XmlSelect,
    XmlSuspend,
    XmlTerm,
    XmlText,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestParse:
    def test_returns_survey_model(self, survey_model: SurveyModel) -> None:
        assert isinstance(survey_model, SurveyModel)

    def test_survey_label(self, survey_model: SurveyModel) -> None:
        assert survey_model.survey_label  # non-empty

    def test_elements_ordered(self, survey_model: SurveyModel) -> None:
        positions = [e.position for e in survey_model.elements]
        assert positions == sorted(positions)

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            xml_parser.parse(Path("nonexistent.xml"))

    def test_malformed_xml(self, tmp_path: Path) -> None:
        from lxml import etree

        bad = tmp_path / "bad.xml"
        bad.write_text("<survey><unclosed>")
        with pytest.raises(etree.XMLSyntaxError):
            xml_parser.parse(bad)


class TestRadio:
    def test_s1_is_radio(self, survey_model: SurveyModel) -> None:
        assert isinstance(survey_model.by_label("S1"), XmlRadio)

    def test_s1_row_count(self, s1_radio: XmlRadio) -> None:
        assert len(s1_radio.rows) == 8

    def test_s1_first_row_text(self, s1_radio: XmlRadio) -> None:
        assert s1_radio.rows[0].text == "United States"

    def test_s1_open_row(self, s1_radio: XmlRadio) -> None:
        open_rows = [r for r in s1_radio.rows if r.is_open]
        assert len(open_rows) == 1
        assert open_rows[0].label == "r8"

    def test_s1_values_order(self, s1_radio: XmlRadio) -> None:
        assert s1_radio.values == "order"

    def test_s2_no_values_attr(self, survey_model: SurveyModel) -> None:
        s2 = survey_model.by_label("S2")
        assert isinstance(s2, XmlRadio)
        assert s2.values is None

    def test_s1_title_stripped(self, s1_radio: XmlRadio) -> None:
        assert "<" not in s1_radio.title
        assert "Where do you live?" in s1_radio.title


class TestCheckbox:
    def test_s4_is_checkbox(self, survey_model: SurveyModel) -> None:
        assert isinstance(survey_model.by_label("S4"), XmlCheckbox)

    def test_s4_atleast(self, s4_checkbox: XmlCheckbox) -> None:
        assert s4_checkbox.atleast == 1

    def test_s4_exclusive_row(self, s4_checkbox: XmlCheckbox) -> None:
        exclusive = [r for r in s4_checkbox.rows if r.is_exclusive]
        assert len(exclusive) == 1
        assert exclusive[0].label == "r10"

    def test_s4_row_count(self, s4_checkbox: XmlCheckbox) -> None:
        assert len(s4_checkbox.rows) == 10

    def test_s7_conditional_display(self, survey_model: SurveyModel) -> None:
        s7 = survey_model.by_label("S7")
        assert isinstance(s7, XmlCheckbox)
        assert s7.cond is not None
        assert "S6" in s7.cond


class TestText:
    def test_contact_name_is_text(self, survey_model: SurveyModel) -> None:
        q = survey_model.by_label("Contact_Name")
        assert isinstance(q, XmlText)

    def test_contact_name_required(self, survey_model: SurveyModel) -> None:
        q = survey_model.by_label("Contact_Name")
        assert isinstance(q, XmlText)
        assert not q.optional

    def test_contact_linkedin_has_optional_in_title(self, survey_model: SurveyModel) -> None:
        """The XML omits optional="1" on Contact_LinkedIn — optionality is indicated
        only in the title text. The parser faithfully reflects that."""
        q = survey_model.by_label("Contact_LinkedIn")
        assert isinstance(q, XmlText)
        assert "optional" in q.title.lower()
        assert not q.optional  # not marked optional="1" in XML


class TestNumber:
    def test_idletime_is_number(self, survey_model: SurveyModel) -> None:
        q = survey_model.by_label("idletime")
        assert isinstance(q, XmlNumber)


class TestSelect:
    def test_timezone_select_is_select(self, survey_model: SurveyModel) -> None:
        q = survey_model.by_label("timeZone_select")
        assert isinstance(q, XmlSelect)

    def test_timezone_choice_count(self, survey_model: SurveyModel) -> None:
        q = survey_model.by_label("timeZone_select")
        assert isinstance(q, XmlSelect)
        assert len(q.choices) == 73

    def test_first_choice_text(self, survey_model: SurveyModel) -> None:
        q = survey_model.by_label("timeZone_select")
        assert isinstance(q, XmlSelect)
        assert "Midway Island" in q.choices[0].text


class TestStructural:
    def test_terms_present(self, survey_model: SurveyModel) -> None:
        terms = survey_model.terms()
        assert len(terms) > 0

    def test_ts1_term(self, survey_model: SurveyModel) -> None:
        term = survey_model.by_label("tS1")
        assert isinstance(term, XmlTerm)
        assert "S1" in term.cond

    def test_quotas_present(self, survey_model: SurveyModel) -> None:
        assert len(survey_model.quotas()) > 0

    def test_suspends_present(self, survey_model: SurveyModel) -> None:
        assert len(survey_model.suspends()) > 0

    def test_goto_present(self, survey_model: SurveyModel) -> None:
        gotos = [e for e in survey_model.elements if isinstance(e, XmlGoto)]
        assert len(gotos) > 0


class TestSurveyModelHelpers:
    def test_by_label_found(self, survey_model: SurveyModel) -> None:
        assert survey_model.by_label("S1") is not None

    def test_by_label_not_found(self, survey_model: SurveyModel) -> None:
        assert survey_model.by_label("DOESNOTEXIST") is None

    def test_questions_returns_only_questions(self, survey_model: SurveyModel) -> None:
        for q in survey_model.questions():
            assert q.tag in {
                "radio", "checkbox", "text", "number", "float",
                "select", "html", "rating", "rank", "ranksort",
            }

    def test_labels_contains_s1(self, survey_model: SurveyModel) -> None:
        assert "S1" in survey_model.labels()

    def test_html_block_parsed(self, survey_model: SurveyModel) -> None:
        q = survey_model.by_label("OptIn2")
        assert isinstance(q, XmlHtml)


class TestDefineInsertExpansion:
    def test_block_questions_flattened(self, survey_model: SurveyModel) -> None:
        # timeZone_select is inside a <block cond="0"> — should still appear
        assert survey_model.by_label("timeZone_select") is not None

    def test_avail_day_checkbox_rows_expanded(self, survey_model: SurveyModel) -> None:
        # availDay uses <insert source="availDays"> — rows should be expanded
        q = survey_model.by_label("availDay")
        assert isinstance(q, XmlCheckbox)
        assert len(q.rows) > 0
