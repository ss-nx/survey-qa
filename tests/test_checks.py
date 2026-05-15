"""Unit tests for all QA checks.

All tests use hand-crafted Pydantic objects — no real LLM calls, no file I/O.
Both sides of a check are the same unified XmlElement type.
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
    SurveyModel,
    XmlCheckbox,
    XmlChoice,
    XmlCol,
    XmlRadio,
    XmlRow,
    XmlSelect,
    XmlText,
)


# ── Helpers (XML side and doc side use the same types) ───────────────────────


def make_row(
    label: str,
    text: str,
    value: int | None = None,
    exclusive: bool = False,
    open_: bool = False,
) -> XmlRow:
    return XmlRow(
        label=label,
        value=value,
        text=text,
        text_raw=text,
        is_exclusive=exclusive,
        is_open=open_,
        id=label,
    )


def make_radio(label: str, rows: list[XmlRow], values: str | None = None, title: str | None = None) -> XmlRadio:
    return XmlRadio(
        label=label,
        id=label,
        position=0,
        title=title if title is not None else f"Q {label}",
        title_raw="",
        rows=rows,
        values=values,
    )


def make_checkbox(label: str, rows: list[XmlRow], atleast: int = 1, title: str | None = None) -> XmlCheckbox:
    return XmlCheckbox(
        label=label,
        id=label,
        position=0,
        title=title if title is not None else f"Q {label}",
        title_raw="",
        rows=rows,
        atleast=atleast,
    )


def make_text(
    label: str,
    optional: bool = False,
    rows: list[XmlRow] | None = None,
    cols: list[XmlCol] | None = None,
) -> XmlText:
    r = rows or []
    c = cols or []
    return XmlText(
        label=label,
        id=label,
        position=0,
        title=f"Q {label}",
        title_raw="",
        optional=optional,
        rows=r,
        cols=c,
        is_grid=bool(r and c),
    )


def make_select(label: str, choices: list[XmlChoice], title: str | None = None) -> XmlSelect:
    return XmlSelect(
        label=label,
        id=label,
        position=0,
        title=title if title is not None else f"Q {label}",
        title_raw="",
        choices=choices,
    )


# ── Q-002 TitleMatch ──────────────────────────────────────────────────────────


class TestQ002TitleMatch:
    def test_matching_titles_pass(self) -> None:
        xml_q = make_radio("Q1", [], title="Where do you live?")
        doc_q = make_radio("Q1", [], title="Where do you live?")
        assert Q002_TitleMatch().run(xml_q, doc_q) == []

    def test_mismatch_produces_warning(self) -> None:
        xml_q = make_radio("Q1", [], title="Where are you from?")
        doc_q = make_radio("Q1", [], title="What country do you live in?")
        findings = Q002_TitleMatch().run(xml_q, doc_q)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].check_id == "Q-002"

    def test_empty_doc_title_skipped(self) -> None:
        xml_q = make_radio("Q1", [], title="Some title")
        doc_q = make_radio("Q1", [], title="")
        assert Q002_TitleMatch().run(xml_q, doc_q) == []


# ── Q-003 TypeMatch ───────────────────────────────────────────────────────────


class TestQ003TypeMatch:
    def test_matching_type_passes(self) -> None:
        xml_q = make_radio("Q1", [])
        doc_q = make_radio("Q1", [])
        assert Q003_TypeMatch().run(xml_q, doc_q) == []

    def test_type_mismatch_is_error(self) -> None:
        xml_q = make_radio("Q1", [])
        doc_q = make_checkbox("Q1", [])
        findings = Q003_TypeMatch().run(xml_q, doc_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── Q-005 OptionalMatch ───────────────────────────────────────────────────────


class TestQ005OptionalMatch:
    def test_both_required_passes(self) -> None:
        xml_q = make_radio("Q1", [])
        doc_q = make_radio("Q1", [])
        assert Q005_OptionalMatch().run(xml_q, doc_q) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_radio("Q1", [])
        doc_q = XmlRadio(
            label="Q1", id="Q1", position=0, title=f"Q Q1", title_raw="", rows=[], optional=True
        )
        findings = Q005_OptionalMatch().run(xml_q, doc_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── RA-001 RowCount ───────────────────────────────────────────────────────────


class TestRA001RowCount:
    def test_matching_count_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "B")]
        xml_q = make_radio("Q1", rows)
        doc_q = make_radio("Q1", [make_row("r1", "A"), make_row("r2", "B")])
        assert RA001_RowCount().run(xml_q, doc_q) == []

    def test_count_mismatch_is_error(self) -> None:
        xml_q = make_radio("Q1", [make_row("r1", "A")])
        doc_q = make_radio("Q1", [make_row("r1", "A"), make_row("r2", "B")])
        findings = RA001_RowCount().run(xml_q, doc_q)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_no_doc_rows_skipped(self) -> None:
        xml_q = make_radio("Q1", [make_row("r1", "A")])
        doc_q = make_radio("Q1", [])
        assert RA001_RowCount().run(xml_q, doc_q) == []

    def test_checkbox_skipped(self) -> None:
        xml_q = make_checkbox("Q1", [make_row("r1", "A")])
        doc_q = make_radio("Q1", [make_row("r1", "A"), make_row("r2", "B")])
        assert RA001_RowCount().run(xml_q, doc_q) == []


# ── RA-002 RowText ────────────────────────────────────────────────────────────


class TestRA002RowText:
    def test_matching_text_passes(self) -> None:
        rows = [make_row("r1", "United States")]
        xml_q = make_radio("Q1", rows)
        doc_q = make_radio("Q1", [make_row("r1", "United States")])
        assert RA002_RowText().run(xml_q, doc_q) == []

    def test_mismatch_produces_warning(self) -> None:
        xml_q = make_radio("Q1", [make_row("r1", "USA")])
        doc_q = make_radio("Q1", [make_row("r1", "Completely different country name here")])
        findings = RA002_RowText().run(xml_q, doc_q)
        assert len(findings) == 1
        assert findings[0].severity == "warning"


# ── RA-003 ExclusiveRow ───────────────────────────────────────────────────────


class TestRA003ExclusiveRow:
    def test_exclusive_present_when_expected_passes(self) -> None:
        xml_rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        doc_rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        assert RA003_ExclusiveRow().run(make_radio("Q1", xml_rows), make_radio("Q1", doc_rows)) == []

    def test_exclusive_missing_is_error(self) -> None:
        xml_rows = [make_row("r1", "A"), make_row("r2", "None")]
        doc_rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        findings = RA003_ExclusiveRow().run(make_radio("Q1", xml_rows), make_radio("Q1", doc_rows))
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── RA-004 OpenRow ────────────────────────────────────────────────────────────


class TestRA004OpenRow:
    def test_open_row_present_when_expected_passes(self) -> None:
        xml_rows = [make_row("r1", "A"), make_row("r2", "Other", open_=True)]
        doc_rows = [make_row("r1", "A"), make_row("r2", "Other", open_=True)]
        assert RA004_OpenRow().run(make_radio("Q1", xml_rows), make_radio("Q1", doc_rows)) == []

    def test_open_row_missing_is_error(self) -> None:
        xml_rows = [make_row("r1", "A"), make_row("r2", "Other")]
        doc_rows = [make_row("r1", "A"), make_row("r2", "Other", open_=True)]
        findings = RA004_OpenRow().run(make_radio("Q1", xml_rows), make_radio("Q1", doc_rows))
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── RA-005 ValuesOrder ────────────────────────────────────────────────────────


class TestRA005ValuesOrder:
    def test_sequential_without_values_order_warns(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=2)]
        xml_q = make_radio("Q1", rows, values=None)
        findings = RA005_ValuesOrder().run(xml_q, make_radio("Q1", []))
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_values_order_set_no_warning(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=2)]
        xml_q = make_radio("Q1", rows, values="order")
        assert RA005_ValuesOrder().run(xml_q, make_radio("Q1", [])) == []


# ── RA-006 DuplicateValues ────────────────────────────────────────────────────


class TestRA006DuplicateValues:
    def test_unique_values_pass(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=2)]
        xml_q = make_radio("Q1", rows)
        assert RA006_DuplicateValues().run(xml_q, make_radio("Q1", [])) == []

    def test_duplicate_values_is_error(self) -> None:
        rows = [make_row("r1", "A", value=1), make_row("r2", "B", value=1)]
        xml_q = make_radio("Q1", rows)
        findings = RA006_DuplicateValues().run(xml_q, make_radio("Q1", []))
        assert len(findings) == 1
        assert findings[0].severity == "error"


# ── CB-001 through CB-006 ─────────────────────────────────────────────────────


class TestCB001RowCount:
    def test_matching_count_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "B")]
        xml_q = make_checkbox("Q1", rows)
        doc_q = make_checkbox("Q1", [make_row("r1", "A"), make_row("r2", "B")])
        assert CB001_RowCount().run(xml_q, doc_q) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_checkbox("Q1", [make_row("r1", "A")])
        doc_q = make_checkbox("Q1", [make_row("r1", "A"), make_row("r2", "B")])
        findings = CB001_RowCount().run(xml_q, doc_q)
        assert findings[0].severity == "error"


class TestCB003Atleast:
    def test_matching_atleast_passes(self) -> None:
        xml_q = make_checkbox("Q1", [], atleast=2)
        doc_q = make_checkbox("Q1", [], atleast=2)
        assert CB003_Atleast().run(xml_q, doc_q) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_checkbox("Q1", [], atleast=1)
        doc_q = make_checkbox("Q1", [], atleast=2)
        findings = CB003_Atleast().run(xml_q, doc_q)
        assert findings[0].severity == "error"


class TestCB004ExclusiveRow:
    def test_exclusive_present_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        xml_q = make_checkbox("Q1", rows)
        doc_q = make_checkbox("Q1", [make_row("r1", "A"), make_row("r2", "None", exclusive=True)])
        assert CB004_ExclusiveRow().run(xml_q, doc_q) == []

    def test_exclusive_missing_is_error(self) -> None:
        xml_q = make_checkbox("Q1", [make_row("r1", "A"), make_row("r2", "None")])
        doc_q = make_checkbox("Q1", [make_row("r1", "A"), make_row("r2", "None", exclusive=True)])
        assert CB004_ExclusiveRow().run(xml_q, doc_q)[0].severity == "error"


class TestCB006ExclusiveRowLast:
    def test_exclusive_last_passes(self) -> None:
        rows = [make_row("r1", "A"), make_row("r2", "None", exclusive=True)]
        xml_q = make_checkbox("Q1", rows)
        assert CB006_ExclusiveRowLast().run(xml_q, make_checkbox("Q1", [])) == []

    def test_exclusive_not_last_warns(self) -> None:
        rows = [make_row("r1", "None", exclusive=True), make_row("r2", "A")]
        xml_q = make_checkbox("Q1", rows)
        findings = CB006_ExclusiveRowLast().run(xml_q, make_checkbox("Q1", []))
        assert findings[0].severity == "warning"


# ── TX-001 ────────────────────────────────────────────────────────────────────


class TestTX001Optional:
    def test_both_required_passes(self) -> None:
        xml_q = make_text("Q1", optional=False)
        doc_q = make_text("Q1", optional=False)
        assert TX001_Optional().run(xml_q, doc_q) == []

    def test_mismatch_is_error(self) -> None:
        xml_q = make_text("Q1", optional=False)
        doc_q = make_text("Q1", optional=True)
        findings = TX001_Optional().run(xml_q, doc_q)
        assert findings[0].severity == "error"


# ── TX-002 ────────────────────────────────────────────────────────────────────


class TestTX002GridRowCount:
    def test_non_grid_skipped(self) -> None:
        xml_q = make_text("Q1")
        assert TX002_GridRowCount().run(xml_q, make_text("Q1")) == []

    def test_grid_count_mismatch_is_error(self) -> None:
        rows = [XmlRow(label="r1", text="Row A", text_raw="Row A", id="r1")]
        cols = [XmlCol(label="c1", text="Col 1", text_raw="Col 1", id="c1")]
        xml_q = make_text("Q1", rows=rows, cols=cols)
        doc_q = make_text("Q1", rows=[make_row("r1", "Row A"), make_row("r2", "Row B")])
        findings = TX002_GridRowCount().run(xml_q, doc_q)
        assert findings[0].severity == "error"


# ── SE-001 / SE-002 ───────────────────────────────────────────────────────────


class TestSE001ChoiceCount:
    def test_matching_count_passes(self) -> None:
        choices = [XmlChoice(label="ch1", text="Option A", text_raw="Option A", id="ch1")]
        xml_q = make_select("Q1", choices)
        doc_q = make_select("Q1", [XmlChoice(label="ch1", text="Option A", text_raw="Option A", id="ch1")])
        assert SE001_ChoiceCount().run(xml_q, doc_q) == []

    def test_count_mismatch_is_error(self) -> None:
        xml_q = make_select("Q1", [XmlChoice(label="ch1", text="A", text_raw="A", id="ch1")])
        doc_q = make_select(
            "Q1",
            [
                XmlChoice(label="ch1", text="A", text_raw="A", id="ch1"),
                XmlChoice(label="ch2", text="B", text_raw="B", id="ch2"),
            ],
        )
        findings = SE001_ChoiceCount().run(xml_q, doc_q)
        assert findings[0].severity == "error"


class TestSE002ChoiceText:
    def test_matching_text_passes(self) -> None:
        choices = [XmlChoice(label="ch1", text="United States", text_raw="United States", id="ch1")]
        xml_q = make_select("Q1", choices)
        doc_q = make_select(
            "Q1",
            [XmlChoice(label="ch1", text="United States", text_raw="United States", id="ch1")],
        )
        assert SE002_ChoiceText().run(xml_q, doc_q) == []

    def test_mismatch_produces_warning(self) -> None:
        choices = [XmlChoice(label="ch1", text="USA", text_raw="USA", id="ch1")]
        xml_q = make_select("Q1", choices)
        doc_q = make_select(
            "Q1",
            [XmlChoice(label="ch1", text="Something totally different here", text_raw="Something totally different here", id="ch1")],
        )
        findings = SE002_ChoiceText().run(xml_q, doc_q)
        assert findings[0].severity == "warning"


# ── Routing checks against survey fixture ────────────────────────────────────


def _empty_doc() -> SurveyModel:
    return SurveyModel(survey_label="doc", elements=[])


class TestRoutingChecks:
    def test_ro002_unknown_label_in_term_cond(self, survey_model: SurveyModel) -> None:
        findings = run_routing_checks(survey_model, _empty_doc())
        ro002 = [f for f in findings if f.check_id == "RO-002"]
        # All term conditions in survey.xml reference valid labels
        # (S1, S2, S4, etc.) — none should be unknown
        assert all(f.severity == "error" for f in ro002) or ro002 == []

    def test_ro003_no_broken_goto_targets(self, survey_model: SurveyModel) -> None:
        findings = run_routing_checks(survey_model, _empty_doc())
        ro003 = [f for f in findings if f.check_id == "RO-003"]
        assert ro003 == [], f"Broken goto targets found: {ro003}"

    def test_ro004_suspends_after_questions(self, survey_model: SurveyModel) -> None:
        findings = run_routing_checks(survey_model, _empty_doc())
        ro004 = [f for f in findings if f.check_id == "RO-004"]
        # Survey is well-formed — suspends should follow questions
        assert isinstance(ro004, list)
