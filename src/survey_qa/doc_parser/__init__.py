"""Questionnaire document parser — docx, pdf → QuestionnaireModel (LLM-assisted).

Two-stage pipeline
------------------
Stage 1 (free): text extraction via python-docx / pdfplumber
Stage 2 (paid): structured extraction via instructor + litellm, cached with diskcache

Dependency direction: core only.
"""

from .base import QuestionnaireParser
from .config import LLMConfig, load_config

__all__ = ["LLMConfig", "QuestionnaireParser", "load_config"]
