"""Decipher XML survey parser.

Walks the XML in document order and produces a SurveyModel.
No LLM involved — lxml only.

Dependency direction: core only.
"""

from __future__ import annotations

import logging
from pathlib import Path

from lxml import etree

from ..core.models import (
    SurveyModel,
    XmlCheckbox,
    XmlChoice,
    XmlCol,
    XmlFloat,
    XmlGoto,
    XmlHtml,
    XmlNumber,
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
from ..core.utils import strip_html

log = logging.getLogger(__name__)


def parse(path: Path | str) -> SurveyModel:
    """Parse a Decipher XML file and return a SurveyModel.

    Raises:
        lxml.etree.XMLSyntaxError: if the file is malformed.
        FileNotFoundError: if path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    tree = etree.parse(str(path))  # raises XMLSyntaxError on bad XML
    root = tree.getroot()

    label = root.get("name") or root.get("alt") or path.stem

    # First pass: collect all <define> elements for insert expansion
    define_registry: dict[str, list[etree._Element]] = {}
    for el in root.iter("define"):
        define_registry[el.get("label", "")] = list(el)

    parser = _SurveyParser(define_registry)
    elements = parser.walk(root, position_start=0)

    return SurveyModel(survey_label=label, elements=elements)


class _SurveyParser:
    """Stateful walker that converts XML elements to model objects."""

    _QUESTION_HANDLERS = {
        "radio": "_parse_radio",
        "checkbox": "_parse_checkbox",
        "text": "_parse_text",
        "number": "_parse_number",
        "float": "_parse_float",
        "select": "_parse_select",
        "html": "_parse_html",
        "rating": "_parse_rating",
        "rank": "_parse_rank",
        "ranksort": "_parse_ranksort",
    }

    _STRUCTURAL_HANDLERS = {
        "term": "_parse_term",
        "quota": "_parse_quota",
        "goto": "_parse_goto",
        "suspend": "_parse_suspend",
    }

    _SKIP_TAGS = frozenset(
        {"res", "style", "samplesources", "samplesource", "condition", "note", "exec", "define"}
    )

    def __init__(self, define_registry: dict[str, list[etree._Element]]) -> None:
        self._defines = define_registry

    def walk(self, parent: etree._Element, position_start: int) -> list:
        """Walk direct children of *parent*, returning a flat list of model objects."""
        elements = []
        pos = position_start

        for el in parent:
            tag = etree.QName(el.tag).localname if isinstance(el.tag, str) else None
            if tag is None or tag in self._SKIP_TAGS:
                continue

            if tag == "block":
                children = self.walk(el, position_start=pos)
                elements.extend(children)
                pos += len(children)
                continue

            handler_name = self._QUESTION_HANDLERS.get(tag) or self._STRUCTURAL_HANDLERS.get(tag)
            if handler_name:
                obj = getattr(self, handler_name)(el, pos)
                if obj is not None:
                    elements.append(obj)
                    pos += 1
            else:
                log.debug("Skipping unknown tag <%s> id=%s", tag, el.get("id", ""))

        return elements

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _get_title(self, el: etree._Element) -> tuple[str, str]:
        title_el = el.find("title")
        if title_el is None:
            return "", ""
        raw = (title_el.text or "") + "".join(
            etree.tostring(child, encoding="unicode") for child in title_el
        )
        return strip_html(raw), raw

    def _get_validate(self, el: etree._Element) -> str | None:
        v = el.find("validate")
        return v.text.strip() if v is not None and v.text else None

    def _get_exec(self, el: etree._Element) -> str | None:
        e = el.find("exec")
        return e.text.strip() if e is not None and e.text else None

    def _get_rows(self, el: etree._Element) -> list[XmlRow]:
        rows: list[XmlRow] = []
        for child in el:
            child_tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else None
            if child_tag == "row":
                rows.append(self._parse_row(child))
            elif child_tag == "insert":
                source = child.get("source", "")
                for defined_row in self._defines.get(source, []):
                    if etree.QName(defined_row.tag).localname == "row":
                        rows.append(self._parse_row(defined_row))
        return rows

    def _get_cols(self, el: etree._Element) -> list[XmlCol]:
        return [self._parse_col(child) for child in el if self._local(child) == "col"]

    @staticmethod
    def _local(el: etree._Element) -> str:
        return etree.QName(el.tag).localname if isinstance(el.tag, str) else ""

    @staticmethod
    def _parse_row(el: etree._Element) -> XmlRow:
        raw = el.text or ""
        return XmlRow(
            label=el.get("label", ""),
            value=int(el.get("value")) if el.get("value") is not None else None,
            text=strip_html(raw),
            text_raw=raw,
            is_exclusive=el.get("exclusive", "0") == "1",
            is_open=el.get("open", "0") == "1",
            open_size=int(el.get("openSize")) if el.get("openSize") is not None else None,
            row_cond=el.get("rowCond") or el.get("cond") or None,
            id=el.get("id", ""),
        )

    @staticmethod
    def _parse_col(el: etree._Element) -> XmlCol:
        raw = el.text or ""
        return XmlCol(
            label=el.get("label", ""),
            text=strip_html(raw),
            text_raw=raw,
            id=el.get("id", ""),
        )

    def _base_kwargs(self, el: etree._Element, pos: int) -> dict:
        title, title_raw = self._get_title(el)
        return dict(
            label=el.get("label", ""),
            id=el.get("id", ""),
            position=pos,
            title=title,
            title_raw=title_raw,
            cond=el.get("cond") or None,
            where=el.get("where", "survey"),
            optional=el.get("optional", "0") not in ("0", None, ""),
            translateable=el.get("translateable", "1") not in ("0",),
            sst=el.get("sst", "1") not in ("0",),
            rows=self._get_rows(el),
            cols=self._get_cols(el),
            validate_src=self._get_validate(el),
            exec_src=self._get_exec(el),
        )

    # ── Question handlers ─────────────────────────────────────────────────────

    def _parse_radio(self, el: etree._Element, pos: int) -> XmlRadio:
        return XmlRadio(**self._base_kwargs(el, pos), values=el.get("values") or None)

    def _parse_checkbox(self, el: etree._Element, pos: int) -> XmlCheckbox:
        return XmlCheckbox(
            **self._base_kwargs(el, pos),
            atleast=int(el.get("atleast", 1)),
            atmost=int(el.get("atmost")) if el.get("atmost") is not None else None,
        )

    def _parse_text(self, el: etree._Element, pos: int) -> XmlText:
        base = self._base_kwargs(el, pos)
        return XmlText(
            **base,
            size=int(el.get("size", 25)),
            is_grid=bool(base["rows"]) and bool(base["cols"]),
        )

    def _parse_number(self, el: etree._Element, pos: int) -> XmlNumber:
        return XmlNumber(**self._base_kwargs(el, pos), size=int(el.get("size", 25)))

    def _parse_float(self, el: etree._Element, pos: int) -> XmlFloat:
        return XmlFloat(**self._base_kwargs(el, pos), size=int(el.get("size", 25)))

    def _parse_select(self, el: etree._Element, pos: int) -> XmlSelect:
        choices = []
        for child in el:
            if self._local(child) == "choice":
                raw = child.text or ""
                choices.append(
                    XmlChoice(
                        label=child.get("label", ""),
                        value=int(child.get("value")) if child.get("value") is not None else None,
                        text=strip_html(raw),
                        text_raw=raw,
                        id=child.get("id", ""),
                    )
                )
        return XmlSelect(**self._base_kwargs(el, pos), choices=choices)

    def _parse_html(self, el: etree._Element, pos: int) -> XmlHtml:
        raw = el.text or ""
        return XmlHtml(
            tag="html",
            label=el.get("label", ""),
            id=el.get("id", ""),
            position=pos,
            title=strip_html(raw),
            title_raw=raw,
            cond=el.get("cond") or None,
            where=el.get("where", "survey"),
        )

    def _parse_rating(self, el: etree._Element, pos: int) -> XmlRating:
        return XmlRating(**self._base_kwargs(el, pos))

    def _parse_rank(self, el: etree._Element, pos: int) -> XmlRank:
        return XmlRank(**self._base_kwargs(el, pos))

    def _parse_ranksort(self, el: etree._Element, pos: int) -> XmlRanksort:
        return XmlRanksort(**self._base_kwargs(el, pos))

    # ── Structural handlers ───────────────────────────────────────────────────

    def _parse_term(self, el: etree._Element, pos: int) -> XmlTerm:
        return XmlTerm(
            label=el.get("label", ""),
            id=el.get("id", ""),
            position=pos,
            cond=el.get("cond", ""),
            incidence=int(el.get("incidence")) if el.get("incidence") is not None else None,
            text=strip_html(el.text or ""),
        )

    def _parse_quota(self, el: etree._Element, pos: int) -> XmlQuota:
        return XmlQuota(
            label=el.get("label", ""),
            id=el.get("id", ""),
            position=pos,
            sheet=el.get("sheet", ""),
            overquota=el.get("overquota", "noqual"),
        )

    def _parse_goto(self, el: etree._Element, pos: int) -> XmlGoto:
        return XmlGoto(
            id=el.get("id", ""),
            position=pos,
            target=el.get("target", ""),
            cond=el.get("cond") or None,
        )

    def _parse_suspend(self, el: etree._Element, pos: int) -> XmlSuspend:
        return XmlSuspend(id=el.get("id", ""), position=pos)
