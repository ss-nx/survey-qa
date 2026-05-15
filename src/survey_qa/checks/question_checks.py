"""Universal checks that apply to all question types (Q-001 through Q-005)."""

from __future__ import annotations

from ..core.models import Finding, XmlQuestion
from ..core.utils import texts_match
from . import register_check
from .base import Check

# Normalize XML tag → canonical type name (collapsed where appropriate)
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
    """Q-002: Question title text matches the doc side (fuzzy, 90% threshold)."""

    id = "Q-002"
    description = "Question title text matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if not doc_side.title:
            return []
        if not texts_match(xml_side.title, doc_side.title):
            from ..core.utils import fuzzy_match

            score = fuzzy_match(xml_side.title, doc_side.title)
            return [
                self.warning(
                    xml_side.label,
                    f"Title text mismatch (similarity {score:.0f}%)",
                    detail=f"XML: {xml_side.title!r}\nQuestionnaire: {doc_side.title!r}",
                )
            ]
        return []


@register_check
class Q003_TypeMatch(Check):
    """Q-003: Question type in XML matches the doc-side type."""

    id = "Q-003"
    description = "Question type matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        xml_type = _TYPE_MAP.get(xml_side.tag, xml_side.tag)
        doc_type = _TYPE_MAP.get(doc_side.tag, doc_side.tag)
        if xml_type != doc_type:
            return [
                self.error(
                    xml_side.label,
                    f"Type mismatch: XML is '{xml_type}', questionnaire expects '{doc_type}'",
                )
            ]
        return []


@register_check
class Q005_OptionalMatch(Check):
    """Q-005: optional/required setting matches the doc-side spec."""

    id = "Q-005"
    description = "optional flag matches questionnaire"

    def run(self, xml_side: XmlQuestion, doc_side: XmlQuestion) -> list[Finding]:
        if xml_side.optional != doc_side.optional:
            expected = "optional" if doc_side.optional else "required"
            actual = "optional" if xml_side.optional else "required"
            return [
                self.error(
                    xml_side.label,
                    f"Question is {actual} in XML but {expected} in questionnaire",
                )
            ]
        return []
