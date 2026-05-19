"""Questionnaire document parser — docx, pdf → SurveyModel (LLM-assisted).

Two-stage pipeline
------------------
Stage 1 (free):  text extraction via python-docx / pdfplumber, with inline
                 formatting preserved as HTML tags (<b>, <i>, <u>).
Stage 2 (paid):  single litellm call converts the raw text to compact format;
                 compact_parser deterministically builds SurveyModel. Cached
                 with diskcache — re-running on the same document is free.

Dependency direction: core only.
"""

from .base import QuestionnaireParser
from .config import LLMConfig, load_config

__all__ = ["LLMConfig", "QuestionnaireParser", "load_config"]
