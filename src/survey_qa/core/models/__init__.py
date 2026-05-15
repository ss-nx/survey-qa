"""core.models — re-exports all model types from their sub-modules.

Import from here for convenience, or import directly from the sub-module
when you want to be explicit about which family a model belongs to:

    from survey_qa.core.models.xml import XmlRadio, SurveyModel
    from survey_qa.core.models.doc import ParsedQuestion, QuestionnaireModel
    from survey_qa.core.models.finding import Finding
"""

from .doc import ParsedOption, ParsedQuestion, QuestionnaireModel
from .finding import Finding
from .xml import (
    QUESTION_TAGS,
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

__all__ = [
    # doc
    "ParsedOption",
    "ParsedQuestion",
    "QuestionnaireModel",
    # finding
    "Finding",
    # xml
    "QUESTION_TAGS",
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
]
