"""Universal checks that apply to all question types (Q-001 through Q-005)."""

from __future__ import annotations

from ..core.models import Finding, ParsedQuestion, XmlQuestion
from ..core.utils import texts_match
from . import register_check
from .base import Check

_TYPE_MAP: dict[str, str] = {
    "radio": "radio",
    "checkbox": "checkbox",
    "text": "text",
    "number": "number",
    "float": "number",
    "select": "select",
    "html": "html",
    "rating": "rating",
    "rank": "rank",
    "ranksort": "rank",
}


@register_check
class Q002_TitleMatch(Check):
    """Q-002: Question title text matches the questionnaire (fuzzy, 90% threshold)."""

    id = "Q-002"
    description = "Question title text matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not q_q.text:
            return []
        if not texts_match(xml_q.title, q_q.text):
            from ..core.utils import fuzzy_match

            score = fuzzy_match(xml_q.title, q_q.text)
            return [
                self.warning(
                    xml_q.label,
                    f"Title text mismatch (similarity {score:.0f}%)",
                    detail=f"XML: {xml_q.title!r}\nQuestionnaire: {q_q.text!r}",
                )
            ]
        return []


@register_check
class Q003_TypeMatch(Check):
    """Q-003: Question type in XML matches the questionnaire type hint."""

    id = "Q-003"
    description = "Question type matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if not q_q.type_hint:
            return []
        xml_type = _TYPE_MAP.get(xml_q.tag, xml_q.tag)
        q_type = q_q.type_hint.lower().strip()
        if xml_type != q_type:
            return [
                self.error(
                    xml_q.label,
                    f"Type mismatch: XML is '{xml_type}', questionnaire expects '{q_type}'",
                )
            ]
        return []


@register_check
class Q005_OptionalMatch(Check):
    """Q-005: optional/required setting matches the questionnaire spec."""

    id = "Q-005"
    description = "optional flag matches questionnaire"

    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        if xml_q.optional != q_q.optional:
            expected = "optional" if q_q.optional else "required"
            actual = "optional" if xml_q.optional else "required"
            return [
                self.error(
                    xml_q.label,
                    f"Question is {actual} in XML but {expected} in questionnaire",
                )
            ]
        return []
