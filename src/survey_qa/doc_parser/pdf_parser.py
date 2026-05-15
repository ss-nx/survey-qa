"""PDF questionnaire parser."""

from __future__ import annotations

from pathlib import Path

from ..core.models import QuestionnaireModel
from .base import QuestionnaireParser
from .config import LLMConfig, load_config
from .extractor import extract_pdf
from .llm_extractor import extract_questions


class PdfParser(QuestionnaireParser):
    """Parse a PDF questionnaire document into a QuestionnaireModel."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or load_config()

    def parse(self, path: Path) -> QuestionnaireModel:
        text = extract_pdf(path)
        questions = extract_questions(text, self._config)
        return QuestionnaireModel(questions=questions)
