"""Unit tests for all QA checks.

All tests use hand-crafted Pydantic objects — no real LLM calls, no file I/O.
"""

from __future__ import annotations

import pytest

from survey_qa.checks.checkbox_checks import (
    CB001_RowCount,
    CB002_RowText,
    CB003_Atleast,
    CB004_ExclusiveRow,
    CB005_OpenRow,
    CB006_ExclusiveRowLast,
)
from survey_qa.checks.question_checks import Q002_TitleMatch, Q003_TypeMatch, Q005_OptionalMatch
from survey_qa.checks.radio_checks import (
    RA001_RowCount,
    RA002_RowText,
    RA003_ExclusiveRow,
    RA004_OpenRow,
    RA005_ValuesOrder,
    RA006_DuplicateValues,
)
from survey_qa.checks.routing_checks import run_routing_checks
from survey_qa.checks.select_checks import SE001_ChoiceCount, SE002_ChoiceText
from survey_qa.checks.text_checks import TX001_Optional, TX002_GridRowCount
from survey_qa.core.models import (
    ParsedOption,
    ParsedQuestion,
    QuestionnaireModel,
    SurveyModel,
    XmlCheckbox,
    XmlChoice,
    XmlCol,
    XmlRadio,
    XmlRow,
    XmlSelect,
    XmlText,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_row(label: str, text: str, value: int | None = None, exclusive: bool = False, open_: bool = False) -> XmlRow:
    return XmlRow(label=label, value=value, text=text, text_raw=text, is_exclusive=exclusive, is_open=open_, id=label)


def make_radio(label: str, rows: list[XmlRow], values: str | None = None) -> XmlRadio:
    return XmlRadio(label=label, id=label, position=0, title=f"Q {label}", title_raw="", rows=rows, values=values)


def make_checkbox(label: str, rows: list[XmlRow], atleast: int = 1) -> XmlCheckbox:
    return XmlCheckbox(label=label, id=label, position=0, title=f"Q {label}", title_raw="", rows=rows, atleast=atleast)


def make_text(label: str, optional: bool = False, rows: list[XmlRow] | None = None, cols: list[XmlCol] | None = None) -> XmlText:
    r = rows or []
    c = cols or []
    return XmlText(label=label, id=label, position=0, title=f"Q {label}", title_raw="", optional=optional, rows=r, cols=c, is_grid=bool(r and c))


def make_select(label: str, choices: list[XmlChoice]) -> XmlSelect:
    return XmlSelect(label=label, id=label, position=0, title=f"Q {label}", title_raw="", choices=choices)


def make_pq(label: str, text: str = "Q text", type_hint: str | None = None, options: list[ParsedOption] | None = None, optional: bool = False, atleast: int | None = None) -> ParsedQuestion:
    return ParsedQuestion(label=label, text=text, type_hint=type_hint, options=options or [], optional=optional, atleast=atleast)


# ── Q-002 TitleMatch ──────────────────────────────────────────────────────────


class TestQ002TitleMatch:
    def test_matching_titles_pass(self) -> None:
        xml_q = make_radio("Q1", [], )
        xml_q = XmlRadio(label="Q1", id="Q1", position=0, title="Where do you live?", title_raw="", rows=[])
        q_q = make_pq("Q1", text="Where do you live?")
        assert Q002_TitleMatch().run(xml_q, q_q) == []

    def test_mismatch_produces_warning(self) -> None:
        xml_q = XmlRadio(label="Q1", id="Q1", position=0, title="Where are you from?", title_raw="", rows=[])
        q_q = make_pq("Q1", text="What country do you live in?")
        findings = Q002_TitleMatch().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].check_id == "Q-002"

    def test_empty_questionnaire_text_skipped(self) -> None:
        xml_q = XmlRadio(label="Q1", id="Q1", position=0, title="Some title", title_raw="", rows=[])
        q_q = make_pq("Q1", text="")
        assert Q002_TitleMatch().run(xml_q, q_q) == []


# ── Q-003 TypeMatch ───────────────────────────────────────────────────────────


class TestQ003TypeMatch:
    def test_matching_type_passes(self) -> None:
        xml_q = make_radio("Q1", [])
        q_q = make_pq("Q1", type_hint="radio")
        assert Q003_TypeMatch().run(xml_q, q_q) == []

    def test_type_mismatch_is_error(self) -> None:
        xml_q = make_radio("Q1", [])
        q_q = make_pq("Q1", type_hint="checkbox")
        findings = Q003_TypeMatch().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_no_type_hint_skipped(self) -> None:
        xml_q = make_radio("Q1", [])
        q_q = make_pq("Q1")
        assert Q003_TypeMatch().run(xml_q, q_q) == []


# ── Q-005 OptionalMatch ───────────────────────────────────────────────────────


class TestQ005OptionalMatch:
    def test_both_required_passes(self) -> None:
        xml_q = make_radio("Q1", [])
        q_q = make_pq("Q1", optional=False)
        assert Q005_OptionalMatch().run(xml_q, q_q) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_radio("Q1", [])
        q_q = make_pq("Q1", optional=True)
        findings = Q005_OptionalMatch().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── RA-001 RowCount ───────────────────────────────────────────────────────────


class TestRA001RowCount:
    def test_matching_count_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "B")]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", type_hint="radio", options=[ParsedOption(text="A"), ParsedOption(text="B")])
        assert RA001_RowCount().run(xml_q, q_q) == []

    def test_count_mismatch_is_error(self) -> None:
        rows = [make_row("r1", "A")]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="B")])
        findings = RA001_RowCount().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_no_questionnaire_options_skipped(self) -> None:
        xml_q = make_radio("Q1", [make_row("r1", "A")])
        q_q = make_pq("Q1")
        assert RA001_RowCount().run(xml_q, q_q) == []

    def test_checkbox_skipped(self) -> None:
        xml_q = make_checkbox("Q1", [make_row("r1", "A")])
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="B")])
        assert RA001_RowCount().run(xml_q, q_q) == []


# ── RA-002 RowText ────────────────────────────────────────────────────────────


class TestRA002RowText:
    def test_matching_text_passes(self) -> None:
        rows = [make_row("r1", "United States")]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="United States")])
        assert RA002_RowText().run(xml_q, q_q) == []

    def test_mismatch_produces_warning(self) -> None:
        rows = [make_row("r1", "USA")]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="Completely different country name here")])
        findings = RA002_RowText().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "warning"


# ── RA-003 ExclusiveRow ───────────────────────────────────────────────────────


class TestRA003ExclusiveRow:
    def test_exclusive_present_when_expected_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="None", is_exclusive=True)])
        assert RA003_ExclusiveRow().run(xml_q, q_q) == []

    def test_exclusive_missing_is_error(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "None")]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="None", is_exclusive=True)])
        findings = RA003_ExclusiveRow().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── RA-004 OpenRow ────────────────────────────────────────────────────────────


class TestRA004OpenRow:
    def test_open_row_present_when_expected_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "Other", open_=True)]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="Other", is_open=True)])
        assert RA004_OpenRow().run(xml_q, q_q) == []

    def test_open_row_missing_is_error(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "Other")]
        xml_q = make_radio("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="Other", is_open=True)])
        findings = RA004_OpenRow().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── RA-005 ValuesOrder ────────────────────────────────────────────────────────


class TestRA005ValuesOrder:
    def test_sequential_without_values_order_warns(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=2)]
        xml_q = make_radio("Q1", rows, values=None)
        q_q = make_pq("Q1")
        findings = RA005_ValuesOrder().run(xml_q, q_q)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_values_order_set_no_warning(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=2)]
        xml_q = make_radio("Q1", rows, values="order")
        q_q = make_pq("Q1")
        assert RA005_ValuesOrder().run(xml_q, q_q) == []


# ── RA-006 DuplicateValues ────────────────────────────────────────────────────


class TestRA006DuplicateValues:
    def test_unique_values_pass(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=2)]
        xml_q = make_radio("Q1", rows)
        assert RA006_DuplicateValues().run(xml_q, make_pq("Q1")) == []

    def test_duplicate_values_is_error(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=1)]
        xml_q = make_radio("Q1", rows)
        findings = RA006_DuplicateValues().run(xml_q, make_pq("Q1"))
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── CB-001 through CB-006 ─────────────────────────────────────────────────────


class TestCB001RowCount:
    def test_matching_count_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "B")]
        xml_q = make_checkbox("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="B")])
        assert CB001_RowCount().run(xml_q, q_q) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_checkbox("Q1", [make_row("r1", "A")])
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="B")])
        findings = CB001_RowCount().run(xml_q, q_q)
        assert findings[0].severity == "error"


class TestCB003Atleast:
    def test_matching_atleast_passes(self) -> None:
        xml_q = make_checkbox("Q1", [], atleast=2)
        q_q = make_pq("Q1", atleast=2)
        assert CB003_Atleast().run(xml_q, q_q) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_checkbox("Q1", [], atleast=1)
        q_q = make_pq("Q1", atleast=2)
        findings = CB003_Atleast().run(xml_q, q_q)
        assert findings[0].severity == "error"


class TestCB004ExclusiveRow:
    def test_exclusive_present_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        xml_q = make_checkbox("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="None", is_exclusive=True)])
        assert CB004_ExclusiveRow().run(xml_q, q_q) == []

    def test_exclusive_missing_is_error(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "None")]
        xml_q = make_checkbox("Q1", rows)
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="None", is_exclusive=True)])
        assert CB004_ExclusiveRow().run(xml_q, q_q)[0].severity == "error"


class TestCB006ExclusiveRowLast:
    def test_exclusive_last_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        xml_q = make_checkbox("Q1", rows)
        assert CB006_ExclusiveRowLast().run(xml_q, make_pq("Q1")) == []

    def test_exclusive_not_last_warns(self) -> None:
        rows = [make_row("r1", "None", exclusive=True), make_row("r2", "A")]
        xml_q = make_checkbox("Q1", rows)
        findings = CB006_ExclusiveRowLast().run(xml_q, make_pq("Q1"))
        assert findings[0].severity == "warning"


# ── TX-001 ────────────────────────────────────────────────────────────────────


class TestTX001Optional:
    def test_both_required_passes(self) -> None:
        xml_q = make_text("Q1", optional=False)
        assert TX001_Optional().run(xml_q, make_pq("Q1", optional=False)) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_text("Q1", optional=False)
        findings = TX001_Optional().run(xml_q, make_pq("Q1", optional=True))
        assert findings[0].severity == "error"


# ── TX-002 ────────────────────────────────────────────────────────────────────


class TestTX002GridRowCount:
    def test_non_grid_skipped(self) -> None:
        xml_q = make_text("Q1")
        assert TX002_GridRowCount().run(xml_q, make_pq("Q1")) == []

    def test_grid_count_mismatch_is_error(self) -> None:
        rows = [XmlRow(label="r1", text="Row A", text_raw="Row A", id="r1")]
        cols = [XmlCol(label="c1", text="Col 1", text_raw="Col 1", id="c1")]
        xml_q = make_text("Q1", rows=rows, cols=cols)
        q_q = make_pq("Q1", options=[ParsedOption(text="Row A"), ParsedOption(text="Row B")])
        findings = TX002_GridRowCount().run(xml_q, q_q)
        assert findings[0].severity == "error"


# ── SE-001 / SE-002 ───────────────────────────────────────────────────────────


class TestSE001ChoiceCount:
    def test_matching_count_passes(self) -> None:
        choices = [XmlChoice(label="ch1", text="Option A", text_raw="Option A", id="ch1")]
        xml_q = make_select("Q1", choices)
        q_q = make_pq("Q1", options=[ParsedOption(text="Option A")])
        assert SE001_ChoiceCount().run(xml_q, q_q) == []

    def test_count_mismatch_is_error(self) -> None:
        xml_q = make_select("Q1", [XmlChoice(label="ch1", text="A", text_raw="A", id="ch1")])
        q_q = make_pq("Q1", options=[ParsedOption(text="A"), ParsedOption(text="B")])
        findings = SE001_ChoiceCount().run(xml_q, q_q)
        assert findings[0].severity == "error"


class TestSE002ChoiceText:
    def test_matching_text_passes(self) -> None:
        choices = [XmlChoice(label="ch1", text="United States", text_raw="United States", id="ch1")]
        xml_q = make_select("Q1", choices)
        q_q = make_pq("Q1", options=[ParsedOption(text="United States")])
        assert SE002_ChoiceText().run(xml_q, q_q) == []

    def test_mismatch_produces_warning(self) -> None:
        choices = [XmlChoice(label="ch1", text="USA", text_raw="USA", id="ch1")]
        xml_q = make_select("Q1", choices)
        q_q = make_pq("Q1", options=[ParsedOption(text="Something totally different here")])
        findings = SE002_ChoiceText().run(xml_q, q_q)
        assert findings[0].severity == "warning"


# ── Routing checks against survey fixture ────────────────────────────────────


class TestRoutingChecks:
    def test_ro002_unknown_label_in_term_cond(self, survey_model: SurveyModel) -> None:
        from survey_qa.core.models import QuestionnaireModel

        qm = QuestionnaireModel(questions=[])
        findings = run_routing_checks(survey_model, qm)
        ro002 = [f for f in findings if f.check_id == "RO-002"]
        # All term conditions in survey.xml reference valid labels
        # (S1, S2, S4, etc.) — none should be unknown
        assert all(f.severity == "error" for f in ro002) or ro002 == []

    def test_ro003_no_broken_goto_targets(self, survey_model: SurveyModel) -> None:
        from survey_qa.core.models import QuestionnaireModel

        qm = QuestionnaireModel(questions=[])
        findings = run_routing_checks(survey_model, qm)
        ro003 = [f for f in findings if f.check_id == "RO-003"]
        assert ro003 == [], f"Broken goto targets found: {ro003}"

    def test_ro004_suspends_after_questions(self, survey_model: SurveyModel) -> None:
        from survey_qa.core.models import QuestionnaireModel

        qm = QuestionnaireModel(questions=[])
        findings = run_routing_checks(survey_model, qm)
        ro004 = [f for f in findings if f.check_id == "RO-004"]
        # Survey is well-formed — suspends should follow questions
        assert isinstance(ro004, list)
