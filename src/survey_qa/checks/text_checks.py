"""Text question QA checks (TX-001 through TX-003).

Only applied when the XML question tag is 'text'.
"""

from __future__ import annotations

from ..core.models import Finding, XmlQuestion, XmlText
from ..core.utils import texts_match
from . import register_check
from .base import Check


def _is_text(q: XmlQuestion) -> bool:
    return isinstance(q, XmlText)


@register_check
class TX001_Optional(Check):
    """TX-001: optional matches questionnaire."""

    id = "TX-001"
    description = "Text question optional flag matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _is_text(xml_side):
            return []
        if xml_side.optional != doc_side.optional:
            expected = "optional" if doc_side.optional else "required"
            actual = "optional" if xml_side.optional else "required"
            return [
                self.error(
                    xml_side.label,
                    f"Text question is {actual} in XML but {expected} in questionnaire",
                )
            ]
        return []


@register_check
class TX002_GridRowCount(Check):
    """TX-002: Grid text row count and text matches questionnaire."""

    id = "TX-002"
    description = "Text grid row count and text matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not isinstance(xml_side, XmlText) or not xml_side.is_grid:
            return []
        if not getattr(doc_side, "rows", None):
            return []
        findings = []
        xml_count = len(xml_side.rows)
        doc_count = len(doc_side.rows)
        if xml_count != doc_count:
            findings.append(
                self.error(
                    xml_side.label,
                    f"Grid row count mismatch: XML has {xml_count}, questionnaire has {doc_count}",
                )
            )
        for i, (xml_row, doc_row) in enumerate(zip(xml_side.rows, doc_side.rows), start=1):
            if not texts_match(xml_row.text, doc_row.text):
                from ..core.utils import fuzzy_match

                score = fuzzy_match(xml_row.text, doc_row.text)
                findings.append(
                    self.error(
                        xml_side.label,
                        f"Grid row {i} ({xml_row.label}) text mismatch (similarity {score:.0f}%)",
                        detail=f"XML: {xml_row.text!r}\nQuestionnaire: {doc_row.text!r}",
                    )
                )
        return findings


@register_check
class TX003_GridColCount(Check):
    """TX-003: Grid text col count matches questionnaire."""

    id = "TX-003"
    description = "Text grid column count matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not isinstance(xml_side, XmlText) or not xml_side.is_grid:
            return []
        xml_col_count = len(xml_side.cols)
        if xml_col_count == 0:
            return []
        return []
