"""Pydantic models for the Decipher XML side of the pipeline.

Produced by xml_parser.parse(). No LLM, no I/O.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# ── Row / Col / Choice ────────────────────────────────────────────────────────


class XmlRow(BaseModel):
    """A single answer option inside a radio, checkbox, or text-grid question."""

    label: str
    value: int | None = None
    text: str
    text_raw: str
    is_exclusive: bool = False
    is_open: bool = False
    open_size: int | None = None
    row_cond: str | None = None
    id: str


class XmlCol(BaseModel):
    """A column header in a grid question."""

    label: str
    text: str
    text_raw: str
    id: str


class XmlChoice(BaseModel):
    """A <choice> option inside a <select> dropdown."""

    label: str
    value: int | None = None
    text: str
    text_raw: str
    id: str


# ── Base question ─────────────────────────────────────────────────────────────


class XmlQuestion(BaseModel):
    """Common fields shared by all respondent-facing question types."""

    tag: str
    label: str
    id: str
    position: int
    title: str
    title_raw: str
    cond: str | None = None
    where: str = "survey"
    optional: bool = False
    translateable: bool = True
    sst: bool = True
    rows: list[XmlRow] = Field(default_factory=list)
    cols: list[XmlCol] = Field(default_factory=list)
    validate_src: str | None = None
    exec_src: str | None = None


# ── Question subtypes ─────────────────────────────────────────────────────────


class XmlRadio(XmlQuestion):
    tag: Literal["radio"] = "radio"
    values: str | None = None


class XmlCheckbox(XmlQuestion):
    tag: Literal["checkbox"] = "checkbox"
    atleast: int = 1
    atmost: int | None = None


class XmlText(XmlQuestion):
    tag: Literal["text"] = "text"
    size: int = 25
    is_grid: bool = False


class XmlNumber(XmlQuestion):
    tag: Literal["number"] = "number"
    size: int = 25


class XmlFloat(XmlQuestion):
    tag: Literal["float"] = "float"
    size: int = 25


class XmlSelect(XmlQuestion):
    tag: Literal["select"] = "select"
    choices: list[XmlChoice] = Field(default_factory=list)


class XmlHtml(XmlQuestion):
    tag: Literal["html"] = "html"


class XmlRating(XmlQuestion):
    tag: Literal["rating"] = "rating"


class XmlRank(XmlQuestion):
    tag: Literal["rank"] = "rank"


class XmlRanksort(XmlQuestion):
    tag: Literal["ranksort"] = "ranksort"


# ── Structural elements ───────────────────────────────────────────────────────


class XmlTerm(BaseModel):
    tag: Literal["term"] = "term"
    label: str
    id: str
    position: int
    cond: str
    incidence: int | None = None
    text: str = ""


class XmlQuota(BaseModel):
    tag: Literal["quota"] = "quota"
    label: str
    id: str
    position: int
    sheet: str = ""
    overquota: str = "noqual"


class XmlGoto(BaseModel):
    tag: Literal["goto"] = "goto"
    id: str
    position: int
    target: str
    cond: str | None = None


class XmlSuspend(BaseModel):
    tag: Literal["suspend"] = "suspend"
    id: str
    position: int


# ── Discriminated union + tag set ─────────────────────────────────────────────


XmlElement = Annotated[
    Union[
        XmlRadio,
        XmlCheckbox,
        XmlText,
        XmlNumber,
        XmlFloat,
        XmlSelect,
        XmlHtml,
        XmlRating,
        XmlRank,
        XmlRanksort,
        XmlTerm,
        XmlQuota,
        XmlGoto,
        XmlSuspend,
    ],
    Field(discriminator="tag"),
]

QUESTION_TAGS: frozenset[str] = frozenset(
    {"radio", "checkbox", "text", "number", "float", "select", "html", "rating", "rank", "ranksort"}
)


# ── Survey container ──────────────────────────────────────────────────────────


class SurveyModel(BaseModel):
    """Top-level container produced by xml_parser.parse()."""

    survey_label: str
    elements: list[XmlElement]

    def questions(self) -> list[XmlQuestion]:
        """Return only respondent-facing question elements, in document order."""
        return [e for e in self.elements if isinstance(e, XmlQuestion)]

    def by_label(self, label: str) -> XmlElement | None:
        """Look up any element by its label attribute."""
        for e in self.elements:
            if getattr(e, "label", None) == label:
                return e
        return None

    def terms(self) -> list[XmlTerm]:
        return [e for e in self.elements if isinstance(e, XmlTerm)]

    def quotas(self) -> list[XmlQuota]:
        return [e for e in self.elements if isinstance(e, XmlQuota)]

    def suspends(self) -> list[XmlSuspend]:
        return [e for e in self.elements if isinstance(e, XmlSuspend)]

    def labels(self) -> set[str]:
        """All element labels present in the survey."""
        return {e.label for e in self.elements if hasattr(e, "label")}
