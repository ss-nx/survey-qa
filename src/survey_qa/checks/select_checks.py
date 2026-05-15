"""Select (dropdown) QA checks (SE-001 through SE-002).

Only applied when the XML question tag is 'select'.
"""

from __future__ import annotations

from ..core.models import Finding, ParsedQuestion, XmlQuestion, XmlSelect
from ..core.utils import texts_match
from . import register_check
from .base import Check


def _is_select(xml_q: XmlQuestion) -> bool:
    return isinstance(xml_q, XmlSelect)


@register_check
class SE001_ChoiceCount(Check):
    """SE-001: Choice count matches questionnaire."""

    id = "SE-001"
    description = "Select choice count matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not isinstance(xml_q, XmlSelect) or not q_q.options:
            return []
        xml_count = len(xml_q.choices)
        q_count = len(q_q.options)
        if xml_count != q_count:
            return [
                self.error(
                    xml_q.label,
                    f"Choice count mismatch: XML has {xml_count}, questionnaire has {q_count}",
                )
            ]
        return []


@register_check
class SE002_ChoiceText(Check):
    """SE-002: Choice text matches per choice (positional, fuzzy 90%)."""

    id = "SE-002"
    description = "Select choice text matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not isinstance(xml_q, XmlSelect) or not q_q.options:
            return []
        findings = []
        for i, (xml_choice, q_opt) in enumerate(zip(xml_q.choices, q_q.options), start=1):
            if not texts_match(xml_choice.text, q_opt.text):
                from ..core.utils import fuzzy_match

                score = fuzzy_match(xml_choice.text, q_opt.text)
                findings.append(
                    self.warning(
                        xml_q.label,
                        f"Choice {i} ({xml_choice.label}) text mismatch (similarity {score:.0f}%)",
                        detail=f"XML: {xml_choice.text!r}\nQuestionnaire: {q_opt.text!r}",
                    )
                )
        return findings
