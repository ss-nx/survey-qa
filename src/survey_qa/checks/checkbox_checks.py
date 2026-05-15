"""Checkbox-specific QA checks (CB-001 through CB-006).

Only applied when the XML question tag is 'checkbox'.
"""

from __future__ import annotations

from ..core.models import Finding, XmlCheckbox, XmlQuestion
from ..core.utils import texts_match
from . import register_check
from .base import Check


def _both_checkbox(xml_side: XmlQuestion, doc_side: XmlQuestion) -> bool:
    return isinstance(xml_side, XmlCheckbox) and isinstance(doc_side, XmlCheckbox)


@register_check
class CB001_RowCount(Check):
    """CB-001: Row count matches questionnaire."""

    id = "CB-001"
    description = "Checkbox row count matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _both_checkbox(xml_side, doc_side) or not doc_side.rows:
            return []
        xml_count = len(xml_side.rows)
        doc_count = len(doc_side.rows)
        if xml_count != doc_count:
            return [
                self.error(
                    xml_side.label,
                    f"Row count mismatch: XML has {xml_count}, questionnaire has {doc_count}",
                )
            ]
        return []


@register_check
class CB002_RowText(Check):
    """CB-002: Row text matches per row (positional, fuzzy 90%)."""

    id = "CB-002"
    description = "Checkbox row text matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _both_checkbox(xml_side, doc_side) or not doc_side.rows:
            return []
        findings = []
        for i, (xml_row, doc_row) in enumerate(zip(xml_side.rows, doc_side.rows), start=1):
            if not texts_match(xml_row.text, doc_row.text):
                from ..core.utils import fuzzy_match

                score = fuzzy_match(xml_row.text, doc_row.text)
                findings.append(
                    self.warning(
                        xml_side.label,
                        f"Row {i} ({xml_row.label}) text mismatch (similarity {score:.0f}%)",
                        detail=f"XML: {xml_row.text!r}\nQuestionnaire: {doc_row.text!r}",
                    )
                )
        return findings


@register_check
class CB003_Atleast(Check):
    """CB-003: atleast value matches questionnaire spec."""

    id = "CB-003"
    description = "Checkbox atleast value matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _both_checkbox(xml_side, doc_side):
            return []
        if xml_side.atleast != doc_side.atleast:
            return [
                self.error(
                    xml_side.label,
                    f"atleast mismatch: XML has atleast={xml_side.atleast}, "
                    f"questionnaire expects {doc_side.atleast}",
                )
            ]
        return []


@register_check
class CB004_ExclusiveRow(Check):
    """CB-004: 'None of the above' / exclusive row has exclusive='1'."""

    id = "CB-004"
    description = "Exclusive row correctly marked in checkbox"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _both_checkbox(xml_side, doc_side) or not doc_side.rows:
            return []
        doc_has_exclusive = any(r.is_exclusive for r in doc_side.rows)
        xml_has_exclusive = any(r.is_exclusive for r in xml_side.rows)
        if doc_has_exclusive and not xml_has_exclusive:
            return [
                self.error(
                    xml_side.label,
                    "Questionnaire has an exclusive option but no row has exclusive='1' in XML",
                )
            ]
        return []


@register_check
class CB005_OpenRow(Check):
    """CB-005: 'Other specify' row has open='1'."""

    id = "CB-005"
    description = "Other-specify row marked open in checkbox"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _both_checkbox(xml_side, doc_side) or not doc_side.rows:
            return []
        doc_has_open = any(r.is_open for r in doc_side.rows)
        xml_has_open = any(r.is_open for r in xml_side.rows)
        if doc_has_open and not xml_has_open:
            return [
                self.error(
                    xml_side.label,
                    "Questionnaire has an 'Other specify' option but no row has open='1' in XML",
                )
            ]
        return []


@register_check
class CB006_ExclusiveRowLast(Check):
    """CB-006: Exclusive row should be the last row in the list."""

    id = "CB-006"
    description = "Exclusive row is last in checkbox list"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not isinstance(xml_side, XmlCheckbox):
            return []
        rows = xml_side.rows
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
                    xml_side.label,
                    f"Exclusive row(s) {labels} are not last in the option list",
                )
            ]
        return []
