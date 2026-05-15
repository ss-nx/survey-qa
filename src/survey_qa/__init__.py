"""Survey QA — Decipher XML vs questionnaire comparison tool.

Public re-exports for convenience. Import directly from sub-modules for clarity:
    from survey_qa.core.models import Finding, SurveyModel
    from survey_qa.xml_parser import parse
    from survey_qa.checks import run_checks
"""

from .core.models import (
    Finding,
    ParserMeta,
    SurveyModel,
)
from . import xml_parser  # noqa: F401 — keeps `from survey_qa import xml_parser` working

__all__ = [
    "Finding",
    "ParserMeta",
    "SurveyModel",
    "xml_parser",
]
