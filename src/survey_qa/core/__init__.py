"""Core shared types — models and utilities.

No business logic. No I/O. Safe to import from any other sub-module.
"""

from .models import (
    Finding,
    ParserMeta,
    SurveyModel,
    XmlCheckbox,
    XmlChoice,
    XmlCol,
    XmlElement,
    XmlFloat,
    XmlGoto,
    XmlHtml,
    XmlNumber,
    XmlQuestion,
    XmlQuota,
    XmlRadio,
    XmlRank,
    XmlRanksort,
    XmlRating,
    XmlRow,
    XmlSelect,
    XmlSuspend,
    XmlTerm,
    XmlText,
)
from .utils import fuzzy_match, strip_html, texts_match

__all__ = [
    "Finding",
    "ParserMeta",
    "SurveyModel",
    "XmlCheckbox",
    "XmlChoice",
    "XmlCol",
    "XmlElement",
    "XmlFloat",
    "XmlGoto",
    "XmlHtml",
    "XmlNumber",
    "XmlQuestion",
    "XmlQuota",
    "XmlRadio",
    "XmlRank",
    "XmlRanksort",
    "XmlRating",
    "XmlRow",
    "XmlSelect",
    "XmlSuspend",
    "XmlTerm",
    "XmlText",
    "fuzzy_match",
    "strip_html",
    "texts_match",
]
