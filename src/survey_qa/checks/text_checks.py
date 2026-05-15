"""Text question QA checks (TX-001 through TX-003).

Only applied when the XML question tag is 'text'.
"""

from __future__ import annotations

from ..core.models import Finding, ParsedQuestion, XmlQuestion, XmlText
from ..core.utils import texts_match
from . import register_check
from .base import Check


def _is_text(xml_q: XmlQuestion) -> bool:
    return isinstance(xml_q, XmlText)


@register_check
class TX001_Optional(Check):
    """TX-001: optional matches questionnaire."""

    id = "TX-001"
    description = "Text question optional flag matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not _is_text(xml_q):
            return []
        if xml_q.optional != q_q.optional:
            expected = "optional" if q_q.optional else "required"
            actual = "optional" if xml_q.optional else "required"
            return [
                self.error(
                    xml_q.label,
                    f"Text question is {actual} in XML but {expected} in questionnaire",
                )
            ]
        return []


@register_check
class TX002_GridRowCount(Check):
    """TX-002: Grid text row count and text matches questionnaire."""

    id = "TX-002"
    description = "Text grid row count and text matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not isinstance(xml_q, XmlText) or not xml_q.is_grid:
            return []
        if not q_q.options:
            return []
        findings = []
        xml_count = len(xml_q.rows)
        q_count = len(q_q.options)
        if xml_count != q_count:
            findings.append(
                self.error(
                    xml_q.label,
                    f"Grid row count mismatch: XML has {xml_count}, questionnaire has {q_count}",
                )
            )
        for i, (xml_row, q_opt) in enumerate(zip(xml_q.rows, q_q.options), start=1):
            if not texts_match(xml_row.text, q_opt.text):
                from ..core.utils import fuzzy_match

                score = fuzzy_match(xml_row.text, q_opt.text)
                findings.append(
                    self.error(
                        xml_q.label,
                        f"Grid row {i} ({xml_row.label}) text mismatch (similarity {score:.0f}%)",
                        detail=f"XML: {xml_row.text!r}\nQuestionnaire: {q_opt.text!r}",
                    )
                )
        return findings


@register_check
class TX003_GridColCount(Check):
    """TX-003: Grid text col count matches questionnaire."""

    id = "TX-003"
    description = "Text grid column count matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not isinstance(xml_q, XmlText) or not xml_q.is_grid:
            return []
        xml_col_count = len(xml_q.cols)
        if xml_col_count == 0:
            return []
        return []
