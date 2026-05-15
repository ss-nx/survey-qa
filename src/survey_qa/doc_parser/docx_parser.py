"""Word (.docx) questionnaire parser."""

from __future__ import annotations

from pathlib import Path

from ..core.models import SurveyModel
from .base import QuestionnaireParser
from .config import LLMConfig, load_config
from .extractor import extract_docx
from .llm_extractor import extract_survey


class DocxParser(QuestionnaireParser):
    """Parse a Word questionnaire document into the unified SurveyModel."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or load_config()

    def parse(self, path: Path) -> SurveyModel:
        text = extract_docx(path)
        return extract_survey(text, self._config)
