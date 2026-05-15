"""Checkbox-specific QA checks (CB-001 through CB-006).

Only applied when the XML question tag is 'checkbox'.
"""

from __future__ import annotations

from ..core.models import Finding, ParsedQuestion, XmlCheckbox, XmlQuestion
from ..core.utils import texts_match
from . import register_check
from .base import Check


def _is_checkbox(xml_q: XmlQuestion) -> bool:
    return isinstance(xml_q, XmlCheckbox)


@register_check
class CB001_RowCount(Check):
    """CB-001: Row count matches questionnaire."""

    id = "CB-001"
    description = "Checkbox row count matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_checkbox(xml_q) or not q_q.options:
            return []
        xml_count = len(xml_q.rows)
        q_count = len(q_q.options)
        if xml_count != q_count:
            return [
                self.error(
                    xml_q.label,
                    f"Row count mismatch: XML has {xml_count}, questionnaire has {q_count}",
                )
            ]
        return []


@register_check
class CB002_RowText(Check):
    """CB-002: Row text matches per row (positional, fuzzy 90%)."""

    id = "CB-002"
    description = "Checkbox row text matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_checkbox(xml_q) or not q_q.options:
            return []
        findings = []
        for i, (xml_row, q_opt) in enumerate(zip(xml_q.rows, q_q.options), start=1):
            if not texts_match(xml_row.text, q_opt.text):
                from ..core.utils import fuzzy_match

                score = fuzzy_match(xml_row.text, q_opt.text)
                findings.append(
                    self.warning(
                        xml_q.label,
                        f"Row {i} ({xml_row.label}) text mismatch (similarity {score:.0f}%)",
                        detail=f"XML: {xml_row.text!r}\nQuestionnaire: {q_opt.text!r}",
                    )
                )
        return findings


@register_check
class CB003_Atleast(Check):
    """CB-003: atleast value matches questionnaire spec."""

    id = "CB-003"
    description = "Checkbox atleast value matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not isinstance(xml_q, XmlCheckbox):
            return []
        if q_q.atleast is None:
            return []
        if xml_q.atleast != q_q.atleast:
            return [
                self.error(
                    xml_q.label,
                    f"atleast mismatch: XML has atleast={xml_q.atleast}, "
                    f"questionnaire expects {q_q.atleast}",
                )
            ]
        return []


@register_check
class CB004_ExclusiveRow(Check):
    """CB-004: 'None of the above' / exclusive row has exclusive='1'."""

    id = "CB-004"
    description = "Exclusive row correctly marked in checkbox"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_checkbox(xml_q) or not q_q.options:
            return []
        q_has_exclusive = any(o.is_exclusive for o in q_q.options)
        xml_has_exclusive = any(r.is_exclusive for r in xml_q.rows)
        if q_has_exclusive and not xml_has_exclusive:
            return [
                self.error(
                    xml_q.label,
                    "Questionnaire has an exclusive option but no row has exclusive='1' in XML",
                )
            ]
        return []


@register_check
class CB005_OpenRow(Check):
    """CB-005: 'Other specify' row has open='1'."""

    id = "CB-005"
    description = "Other-specify row marked open in checkbox"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_checkbox(xml_q) or not q_q.options:
            return []
        q_has_open = any(o.is_open for o in q_q.options)
        xml_has_open = any(r.is_open for r in xml_q.rows)
        if q_has_open and not xml_has_open:
            return [
                self.error(
                    xml_q.label,
                    "Questionnaire has an 'Other specify' option but no row has open='1' in XML",
                )
            ]
        return []


@register_check
class CB006_ExclusiveRowLast(Check):
    """CB-006: Exclusive row should be the last row in the list."""

    id = "CB-006"
    description = "Exclusive row is last in checkbox list"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_checkbox(xml_q):
            return []
        rows = xml_q.rows
        if not rows:
            return []
        exclusive_indices = [i for i, r in enumerate(rows) if r.is_exclusive]
        if not exclusive_indices:
            return []
        last_idx = len(rows) - 1
        non_last = [i for i in exclusive_indices if i != last_idx]
        if non_last:
            labels = [rows[i].label for i in non_last]
            return [
                self.warning(
                    xml_q.label,
                    f"Exclusive row(s) {labels} are not last in the option list",
                )
            ]
        return []
