"""Tests for the compact-format parser."""

from __future__ import annotations

import pytest

from survey_qa.core.models import (
    XmlCheckbox,
    XmlFloat,
    XmlGoto,
    XmlHtml,
    XmlNumber,
    XmlQuota,
    XmlRadio,
    XmlSelect,
    XmlTerm,
    XmlText,
)
from survey_qa.doc_parser.compact_parser import (
    CompactParseError,
    parse_compact,
)


# ── Basic parsing ─────────────────────────────────────────────────────────────


def test_empty_string_yields_empty_model():
    result = parse_compact("")
    assert result.survey_label == "doc"
    assert result.elements == []


def test_whitespace_only_yields_empty_model():
    result = parse_compact("\n\n   \n")
    assert result.elements == []


# ── Radio ─────────────────────────────────────────────────────────────────────


def test_radio_basic():
    text = """## radio
Where do you live?
options:
  1. United States
  2. Canada
"""
    result = parse_compact(text)
    assert len(result.elements) == 1
    q = result.elements[0]
    assert isinstance(q, XmlRadio)
    assert q.tag == "radio"
    assert q.title == "Where do you live?"
    assert q.label == "doc:q1"
    assert q.id == "doc:q1"
    assert q.position == 0
    assert len(q.rows) == 2
    assert q.rows[0].text == "United States"
    assert q.rows[0].label == "r1"
    assert q.rows[0].id == "doc:q1:r1"
    assert q.rows[0].value == 1
    assert q.rows[1].text == "Canada"
    assert q.rows[1].value == 2


def test_radio_with_open_and_exclusive_tags():
    text = """## radio
Pick one
options:
  1. Apple
  2. Other, please specify  [open]
  3. I prefer not to answer  [exclusive]
"""
    result = parse_compact(text)
    q = result.elements[0]
    assert q.rows[0].is_open is False
    assert q.rows[1].is_open is True
    assert q.rows[1].text == "Other, please specify"
    assert q.rows[2].is_exclusive is True


def test_radio_multiple_tags_on_one_option():
    text = """## radio
Pick one
options:
  1. None of the above  [exclusive] [open]
"""
    result = parse_compact(text)
    q = result.elements[0]
    assert q.rows[0].is_exclusive is True
    assert q.rows[0].is_open is True
    assert q.rows[0].text == "None of the above"


def test_radio_with_doc_explicit_codes():
    """The doc may specify non-sequential codes (e.g., 99 for refused)."""
    text = """## radio
Country
options:
  1. USA
  2. Canada
  99. Refused  [exclusive]
"""
    result = parse_compact(text)
    q = result.elements[0]
    assert q.rows[0].value == 1
    assert q.rows[0].text == "USA"
    assert q.rows[2].value == 99
    assert q.rows[2].is_exclusive is True


def test_term_key_flat_row():
    text = """## radio
What is your age?
term: r4
options:
  1. 18-24
  2. 25-34
  3. 35-44
  4. Under 18
"""
    q = parse_compact(text).elements[0]
    notes = q.parser_meta.ambiguity_notes
    assert any("r4" in n for n in notes)


def test_term_key_grid_cell():
    text = """## radio
Rate each brand.
term: r1.c5, r2.c5
cols:
  1. Love it
  2. Like it
  3. Neutral
  4. Dislike it
  5. Hate it
rows:
  1. Apple
  2. Samsung
"""
    q = parse_compact(text).elements[0]
    notes = q.parser_meta.ambiguity_notes
    assert any("r1.c5" in n and "r2.c5" in n for n in notes)


def test_term_key_col_only():
    text = """## radio
Q
term: c5
cols:
  1. A
  2. B
  3. C
  4. D
  5. E
rows:
  1. X
"""
    q = parse_compact(text).elements[0]
    assert any("c5" in n for n in q.parser_meta.ambiguity_notes)


def test_term_key_rejects_bad_token():
    text = """## radio
Q
term: rowFour
options:
  1. A
"""
    with pytest.raises(CompactParseError, match="bad term token"):
        parse_compact(text)


def test_term_key_compound_and():
    text = """## checkbox
Q
term: r3 and r4
options:
  1. A
  2. B
  3. C
  4. D
"""
    q = parse_compact(text).elements[0]
    notes = q.parser_meta.ambiguity_notes
    assert any("r3 and r4" in n for n in notes)


def test_term_key_compound_or():
    text = """## radio
Q
term: r1 or r2 or r3
options:
  1. A
  2. B
  3. C
"""
    q = parse_compact(text).elements[0]
    assert any("r1 or r2 or r3" in n for n in q.parser_meta.ambiguity_notes)


def test_term_key_compound_with_parens():
    text = """## checkbox
Q
term: (r1 and r2) or r3
options:
  1. A
  2. B
  3. C
"""
    q = parse_compact(text).elements[0]
    assert any("(r1 and r2) or r3" in n for n in q.parser_meta.ambiguity_notes)


def test_term_key_negation():
    text = """## radio
Q
term: not r1
options:
  1. A
  2. B
"""
    q = parse_compact(text).elements[0]
    assert any("not r1" in n for n in q.parser_meta.ambiguity_notes)


def test_term_key_grid_cell_compound():
    text = """## checkbox
Rate each brand.
term: r1.c5 and r2.c5
cols:
  1. Love
  2. Like
  3. Neutral
  4. Dislike
  5. Hate
rows:
  1. Apple
  2. Samsung
"""
    q = parse_compact(text).elements[0]
    assert any("r1.c5 and r2.c5" in n for n in q.parser_meta.ambiguity_notes)


def test_radio_meta_has_doc_source():
    text = """## radio
Q
options:
  1. A
"""
    q = parse_compact(text).elements[0]
    assert q.parser_meta is not None
    assert q.parser_meta.source == "doc"
    assert q.parser_meta.confidence == 1.0


# ── Checkbox ──────────────────────────────────────────────────────────────────


def test_checkbox_default_atleast():
    text = """## checkbox
Pick all
options:
  1. A
  2. B
"""
    q = parse_compact(text).elements[0]
    assert isinstance(q, XmlCheckbox)
    assert q.atleast == 1


def test_checkbox_explicit_atleast():
    text = """## checkbox
Pick at least 2
atleast: 2
options:
  1. A
  2. B
  3. C
"""
    q = parse_compact(text).elements[0]
    assert q.atleast == 2


def test_checkbox_bad_atleast_raises():
    text = """## checkbox
Q
atleast: not-an-int
options:
  1. A
"""
    with pytest.raises(CompactParseError, match="atleast"):
        parse_compact(text)


# ── Text ──────────────────────────────────────────────────────────────────────


def test_text_basic():
    text = """## text
Describe your experience.
"""
    q = parse_compact(text).elements[0]
    assert isinstance(q, XmlText)
    assert q.title == "Describe your experience."
    assert q.is_grid is False


def test_text_optional_flag():
    text = """## text
Tell us more.
flags: optional
"""
    q = parse_compact(text).elements[0]
    assert q.optional is True


def test_text_grid():
    text = """## text
For each item, write a reaction.
rows:
  1. Customer service
  2. Product quality
"""
    q = parse_compact(text).elements[0]
    assert q.is_grid is True
    assert len(q.rows) == 2


# ── Number / Float ────────────────────────────────────────────────────────────


def test_number():
    q = parse_compact("## number\nHow many?\n").elements[0]
    assert isinstance(q, XmlNumber)
    assert q.title == "How many?"


def test_float():
    q = parse_compact("## float\nWhat percent?\n").elements[0]
    assert isinstance(q, XmlFloat)


# ── Select ────────────────────────────────────────────────────────────────────


def test_select_with_choices():
    text = """## select
State of residence
choices:
  1. Alabama
  2. Alaska
"""
    q = parse_compact(text).elements[0]
    assert isinstance(q, XmlSelect)
    assert len(q.choices) == 2
    assert q.choices[0].text == "Alabama"
    assert q.choices[0].value == 1
    assert q.choices[0].id == "doc:q1:c1"


# ── HTML ──────────────────────────────────────────────────────────────────────


def test_html():
    text = """## html
Welcome to the survey.
"""
    q = parse_compact(text).elements[0]
    assert isinstance(q, XmlHtml)
    assert q.title == "Welcome to the survey."


# ── Term ──────────────────────────────────────────────────────────────────────


def test_term():
    text = """## term
You must be 18+.
display: if Q1 < 18
"""
    e = parse_compact(text).elements[0]
    assert isinstance(e, XmlTerm)
    assert e.text == "You must be 18+."
    assert e.cond == "if Q1 < 18"


def test_term_without_display_has_empty_cond():
    e = parse_compact("## term\nScreen-out.\n").elements[0]
    assert isinstance(e, XmlTerm)
    assert e.cond == ""


# ── Quota ─────────────────────────────────────────────────────────────────────


def test_quota():
    text = """## quota
sheet: Age Quotas
overquota: term_overquota
"""
    e = parse_compact(text).elements[0]
    assert isinstance(e, XmlQuota)
    assert e.sheet == "Age Quotas"
    assert e.overquota == "term_overquota"


def test_quota_default_overquota():
    e = parse_compact("## quota\nsheet: X\n").elements[0]
    assert e.overquota == "noqual"


# ── Goto ──────────────────────────────────────────────────────────────────────


def test_goto():
    text = """## goto
target: end
display: if S1 = "no"
"""
    e = parse_compact(text).elements[0]
    assert isinstance(e, XmlGoto)
    assert e.target == "end"
    assert e.cond == 'if S1 = "no"'


def test_goto_without_target_raises():
    with pytest.raises(CompactParseError, match="target"):
        parse_compact("## goto\ndisplay: foo\n")


# ── Suspend (no longer a doc-side type) ──────────────────────────────────────


def test_suspend_block_rejected():
    with pytest.raises(CompactParseError, match="unknown type"):
        parse_compact("## suspend\n")


# ── Grids ─────────────────────────────────────────────────────────────────────


def test_radio_grid_has_rows_and_cols():
    text = """## radio
Rate each brand.
cols:
  1. Bad
  2. OK
  3. Good
rows:
  1. Apple
  2. Samsung
"""
    q = parse_compact(text).elements[0]
    assert len(q.rows) == 2
    assert len(q.cols) == 3
    assert q.cols[0].text == "Bad"
    assert q.cols[0].label == "c1"
    assert q.cols[0].id == "doc:q1:c1"


# ── Display logic ─────────────────────────────────────────────────────────────


def test_display_logic_lands_in_parser_meta_not_cond():
    text = """## radio
Q
display: if S1 = "yes"
options:
  1. A
"""
    q = parse_compact(text).elements[0]
    assert q.cond is None
    assert q.parser_meta.raw_display_logic == 'if S1 = "yes"'


# ── Notes and unknown keys ────────────────────────────────────────────────────


def test_note_lands_in_ambiguity_notes():
    text = """## radio
Q
note: parsed options from inline paragraph
options:
  1. A
"""
    q = parse_compact(text).elements[0]
    assert "parsed options from inline paragraph" in q.parser_meta.ambiguity_notes


def test_unknown_key_preserved_as_ambiguity_note():
    text = """## radio
Q
mystery_key: some value
options:
  1. A
"""
    q = parse_compact(text).elements[0]
    assert any("mystery_key" in n for n in q.parser_meta.ambiguity_notes)


# ── Multiple blocks ───────────────────────────────────────────────────────────


def test_multiple_blocks_in_document_order():
    text = """## radio
Q1
options:
  1. Yes
  2. No

## text
Q2 — describe

## number
How many?
"""
    result = parse_compact(text)
    assert len(result.elements) == 3
    assert result.elements[0].position == 0
    assert result.elements[1].position == 1
    assert result.elements[2].position == 2
    assert result.elements[0].label == "doc:q1"
    assert result.elements[1].label == "doc:q2"
    assert result.elements[2].label == "doc:q3"


def test_multiline_title():
    text = """## radio
This is a long question
that wraps to a second line.
options:
  1. Yes
  2. No
"""
    q = parse_compact(text).elements[0]
    assert "long question" in q.title
    assert "second line" in q.title


# ── Error cases ───────────────────────────────────────────────────────────────


def test_unknown_type_raises():
    with pytest.raises(CompactParseError, match="unknown type"):
        parse_compact("## mystery\nQ\n")


def test_orphan_list_item_raises():
    text = """## radio
Q
  1. orphan
"""
    with pytest.raises(CompactParseError, match="no preceding list key"):
        parse_compact(text)


def test_duplicate_list_key_raises():
    text = """## radio
Q
options:
  1. A
options:
  2. B
"""
    with pytest.raises(CompactParseError, match="duplicate"):
        parse_compact(text)


def test_inline_value_on_list_key_raises():
    text = """## radio
Q
options: should-not-be-here
"""
    with pytest.raises(CompactParseError, match="inline value"):
        parse_compact(text)


def test_text_after_keys_raises():
    text = """## radio
Q
options:
  1. A
trailing prose
"""
    with pytest.raises(CompactParseError, match="unexpected text"):
        parse_compact(text)


def test_bullet_dash_no_longer_accepted():
    """Old syntax '- text' should now be rejected as a list item."""
    text = """## radio
Q
options:
  - A
"""
    # The dash line is no longer a list item, so it's treated as "unexpected
    # text after keys/lists" — the error confirms the old syntax is dead.
    with pytest.raises(CompactParseError):
        parse_compact(text)


# ── Explicit labels in header ─────────────────────────────────────────────────


def test_explicit_label_used():
    text = """## radio [S1]
Where do you live?
options:
  1. USA
  2. Canada
"""
    q = parse_compact(text).elements[0]
    assert q.label == "S1"
    assert q.id == "doc:S1"
    assert q.rows[0].id == "doc:S1:r1"


def test_explicit_label_with_underscore():
    text = """## radio [Awareness_Q1]
Title
options:
  1. A
"""
    q = parse_compact(text).elements[0]
    assert q.label == "Awareness_Q1"
    assert q.id == "doc:Awareness_Q1"


def test_no_label_falls_back_to_synthetic():
    text = """## radio
Q
options:
  1. A
"""
    q = parse_compact(text).elements[0]
    assert q.label == "doc:q1"


def test_explicit_label_term_block():
    text = """## term [term_under18]
Must be 18+.
display: if S1 < 18
"""
    e = parse_compact(text).elements[0]
    assert e.label == "term_under18"


def test_mixed_explicit_and_synthetic_labels():
    text = """## radio [S1]
First
options:
  1. A

## radio
Second
options:
  1. B
"""
    elements = parse_compact(text).elements
    assert elements[0].label == "S1"
    assert elements[1].label == "doc:q2"


# ── Inline HTML preservation (formatting / line breaks / bullets) ─────────────


def test_bold_italic_preserved_in_title():
    text = """## radio
Select <b>all</b> that apply to your <i>current</i> situation.
options:
  1. A
"""
    q = parse_compact(text).elements[0]
    assert q.title == "Select <b>all</b> that apply to your <i>current</i> situation."


def test_br_preserved_in_title():
    text = """## radio
For this section,<br>consider only your day job.
options:
  1. Yes
  2. No
"""
    q = parse_compact(text).elements[0]
    assert "<br>" in q.title


def test_bullets_preserved_in_option_text():
    text = """## radio
Question
options:
  1. Includes:<br><ul><li>item A</li><li>item B</li></ul>
  2. Other option
"""
    q = parse_compact(text).elements[0]
    assert "<ul>" in q.rows[0].text
    assert "<li>item A</li>" in q.rows[0].text
    assert q.rows[1].text == "Other option"


def test_inline_br_in_option_text():
    text = """## radio
Q
options:
  1. Long option<br>with a forced break
"""
    q = parse_compact(text).elements[0]
    assert q.rows[0].text == "Long option<br>with a forced break"
