"""Abstract base class and factory for questionnaire document parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..core.models import SurveyModel


class QuestionnaireParser(ABC):
    """Parse a client questionnaire document into a SurveyModel.

    Returns the same unified `SurveyModel` that the XML parser produces,
    so the check layer compares like-typed elements on both sides.
    """

    @abstractmethod
    def parse(self, path: Path) -> SurveyModel: ...

    @classmethod
    def for_file(cls, path: Path) -> "QuestionnaireParser":
        """Factory: return the right parser for the given file extension."""
        suffix = path.suffix.lower()
        if suffix == ".docx":
            from .docx_parser import DocxParser
            return DocxParser()
        if suffix == ".pdf":
            from .pdf_parser import PdfParser
            return PdfParser()
        raise ValueError(f"Unsupported questionnaire format: {suffix!r}")
