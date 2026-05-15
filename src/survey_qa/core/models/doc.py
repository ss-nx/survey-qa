"""Pydantic models for the questionnaire document side of the pipeline.

Produced by doc_parser (LLM-assisted). These are the source of truth
that the check layer validates the XML against.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedOption(BaseModel):
    """A single answer option from the parsed questionnaire document."""

    code: str | None = None
    text: str
    is_exclusive: bool = False
    is_open: bool = False


class ParsedQuestion(BaseModel):
    """A question extracted from the client questionnaire document by the LLM parser."""

    label: str
    text: str
    type_hint: str | None = None
    options: list[ParsedOption] = Field(default_factory=list)
    routing_rules: list[str] = Field(default_factory=list)
    optional: bool = False
    atleast: int | None = None
    confidence: float = 1.0
    source_location: str = ""


class QuestionnaireModel(BaseModel):
    """Top-level container for the parsed questionnaire document."""

    questions: list[ParsedQuestion]

    def by_label(self, label: str) -> ParsedQuestion | None:
        for q in self.questions:
            if q.label == label:
                return q
        return None

    def labels(self) -> set[str]:
        return {q.label for q in self.questions}
