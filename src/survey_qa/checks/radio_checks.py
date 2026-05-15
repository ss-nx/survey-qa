"""Radio-specific QA checks (RA-001 through RA-006).

Only applied when the XML question tag is 'radio'.
"""

from __future__ import annotations

from ..core.models import Finding, ParsedQuestion, XmlQuestion, XmlRadio
from ..core.utils import texts_match
from . import register_check
from .base import Check


def _is_radio(xml_q: XmlQuestion) -> bool:
    return isinstance(xml_q, XmlRadio)


@register_check
class RA001_RowCount(Check):
    """RA-001: Row count matches questionnaire."""

    id = "RA-001"
    description = "Radio row count matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_radio(xml_q) or not q_q.options:
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
class RA002_RowText(Check):
    """RA-002: Row text matches per row (positional, fuzzy 90%)."""

    id = "RA-002"
    description = "Radio row text matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_radio(xml_q) or not q_q.options:
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
class RA003_ExclusiveRow(Check):
    """RA-003: Exclusive/NA row present in XML when expected by questionnaire."""

    id = "RA-003"
    description = "Exclusive row present when questionnaire expects one"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_radio(xml_q) or not q_q.options:
            return []
        q_has_exclusive = any(o.is_exclusive for o in q_q.options)
        xml_has_exclusive = any(r.is_exclusive for r in xml_q.rows)
        if q_has_exclusive and not xml_has_exclusive:
            return [
                self.error(
                    xml_q.label,
                    "Questionnaire has an exclusive/NA option but no row is marked exclusive='1' in XML",
                )
            ]
        return []


@register_check
class RA004_OpenRow(Check):
    """RA-004: 'Other specify' row has open='1' when questionnaire expects one."""

    id = "RA-004"
    description = "Other-specify row marked open in XML"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_radio(xml_q) or not q_q.options:
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
class RA005_ValuesOrder(Check):
    """RA-005: values='order' used when options have sequential numeric values."""

    id = "RA-005"
    description = "values='order' attribute consistent with option values"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not isinstance(xml_q, XmlRadio):
            return []
        rows = xml_q.rows
        if not rows:
            return []
        explicit_values = [r.value for r in rows if r.value is not None]
        sequential = explicit_values == list(range(1, len(explicit_values) + 1))
        has_values_order = xml_q.values == "order"

        if sequential and not has_values_order and len(explicit_values) == len(rows):
            return [
                self.warning(
                    xml_q.label,
                    "Options have sequential values 1…N but values='order' is not set",
                    detail="Consider using values='order' for cleaner XML.",
                )
            ]
        return []


@register_check
class RA006_DuplicateValues(Check):
    """RA-006: No duplicate row value attributes."""

    id = "RA-006"
    description = "No duplicate row values in radio question"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_radio(xml_q):
            return []
        values = [r.value for r in xml_q.rows if r.value is not None]
        seen: set[int] = set()
        dupes: list[int] = []
        for v in values:
            if v in seen:
                dupes.append(v)
            seen.add(v)
        if dupes:
            return [
                self.error(
                    xml_q.label,
                    f"Duplicate row value(s) found: {dupes}",
                )
            ]
        return []
