"""Select (dropdown) QA checks (SE-001 through SE-002).

Only applied when the XML question tag is 'select'.
"""

from __future__ import annotations

from ..core.models import Finding, XmlQuestion, XmlSelect
from ..core.utils import texts_match
from . import register_check
from .base import Check


def _both_select(xml_side: XmlQuestion, doc_side: XmlQuestion) -> bool:
    return isinstance(xml_side, XmlSelect) and isinstance(doc_side, XmlSelect)


@register_check
class SE001_ChoiceCount(Check):
    """SE-001: Choice count matches questionnaire."""

    id = "SE-001"
    description = "Select choice count matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _both_select(xml_side, doc_side) or not doc_side.choices:
            return []
        xml_count = len(xml_side.choices)
        doc_count = len(doc_side.choices)
        if xml_count != doc_count:
            return [
                self.error(
                    xml_side.label,
                    f"Choice count mismatch: XML has {xml_count}, questionnaire has {doc_count}",
                )
            ]
        return []


@register_check
class SE002_ChoiceText(Check):
    """SE-002: Choice text matches per choice (positional, fuzzy 90%)."""

    id = "SE-002"
    description = "Select choice text matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not _both_select(xml_side, doc_side) or not doc_side.choices:
            return []
        findings = []
        for i, (xml_choice, doc_choice) in enumerate(
            zip(xml_side.choices, doc_side.choices), start=1
        ):
            if not texts_match(xml_choice.text, doc_choice.text):
                from ..core.utils import fuzzy_match

                score = fuzzy_match(xml_choice.text, doc_choice.text)
                findings.append(
                    self.warning(
                        xml_side.label,
                        f"Choice {i} ({xml_choice.label}) text mismatch (similarity {score:.0f}%)",
                        detail=f"XML: {xml_choice.text!r}\nQuestionnaire: {doc_choice.text!r}",
                    )
                )
        return findings
