"""Compact-format parser — doc-side text → SurveyModel.

The compact format is the input Claude produces while authoring a doc-side
survey representation. A small block per element captures three things:
question type, title, and option list (with optional tags and keys for
defaults overrides). See docs/08_COMPACT_FORMAT.md for the spec.

The parser is deterministic — no LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.models import (
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
    XmlQuota,
    XmlRadio,
    XmlRow,
    XmlSelect,
    XmlTerm,
    XmlText,
)


class CompactParseError(ValueError):
    """Raised when a compact-format block cannot be parsed."""


_KEY_NAMES = frozenset({"flags", "atleast", "display", "target", "sheet", "overquota", "note", "term"})
_LIST_NAMES = frozenset({"options", "choices", "rows", "cols"})
_VALID_TYPES = frozenset({
    "radio", "checkbox", "text", "number", "float", "select",
    "html", "term", "quota", "goto",
})

_HEADER_RE = re.compile(r"^##\s+(\w+)(?:\s+\[([^\]\s][^\]]*)\])?\s*$")
_KEY_RE = re.compile(r"^([a-z_]+)\s*:\s*(.*)$")
_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")
_TRAILING_TAG_RE = re.compile(r"\s*\[(open|exclusive)\]\s*$")

# Tokens allowed inside a `term:` expression. Coordinates take three shapes
# (rN.cM, rN, cN); the boolean keywords `and`/`or`/`not`, commas, and parens
# combine them into compound conditions. Anything else is rejected.
_TERM_TOKEN_RE = re.compile(
    r"\s*([(),]|\band\b|\bor\b|\bnot\b|r\d+\.c\d+|r\d+|c\d+|\S+)"
)
_TERM_COORD_TOKEN_RE = re.compile(r"^(?:r\d+(?:\.c\d+)?|c\d+)$")
_TERM_KEYWORDS = frozenset({"and", "or", "not"})
_TERM_PUNCT = frozenset({",", "(", ")"})


@dataclass
class _ParsedBlock:
    type_: str
    explicit_label: str | None = None
    title: str = ""
    keys: dict[str, str] = field(default_factory=dict)
    # Each list item is (explicit_code, raw_text_with_trailing_tags).
    lists: dict[str, list[tuple[int, str]]] = field(default_factory=dict)
    extra_keys: dict[str, str] = field(default_factory=dict)
    line_no: int = 0


def parse_compact(text: str) -> SurveyModel:
    """Parse a compact-format document into a doc-side SurveyModel.

    Each block becomes an XmlElement with synthetic id/position/label
    and parser_meta.source = "doc". Auto-generates row labels (r1, r2, ...)
    and row IDs. Raises CompactParseError on malformed input.
    """
    blocks = _split_blocks(text)
    elements: list[XmlElement] = []
    for i, (lines, start_line) in enumerate(blocks):
        pb = _parse_block(lines, start_line)
        elements.append(_build_element(pb, i))
    return SurveyModel(survey_label="doc", elements=elements)


# ── Block splitting ───────────────────────────────────────────────────────────


def _split_blocks(text: str) -> list[tuple[list[str], int]]:
    """Split text into blocks. Each block starts with '## <type>'.

    Returns a list of (lines, starting_line_number_1_indexed) tuples.
    Stray non-blank text outside any block is silently ignored.
    """
    lines = text.splitlines()
    blocks: list[tuple[list[str], int]] = []
    current: list[str] = []
    current_start = 0
    in_block = False

    for idx, raw in enumerate(lines):
        line = raw.rstrip()
        if line.startswith("## "):
            if in_block and current:
                blocks.append((current, current_start))
            current = [line]
            current_start = idx + 1
            in_block = True
        elif in_block:
            if line.strip() == "":
                if current:
                    blocks.append((current, current_start))
                current = []
                in_block = False
            else:
                current.append(line)

    if in_block and current:
        blocks.append((current, current_start))

    return blocks


# ── Block parsing ─────────────────────────────────────────────────────────────


def _parse_block(lines: list[str], start_line: int) -> _ParsedBlock:
    if not lines:
        raise CompactParseError(f"Empty block at line {start_line}")

    header = lines[0]
    m = _HEADER_RE.match(header)
    if not m:
        raise CompactParseError(
            f"Line {start_line}: expected '## <type>' or '## <type> [label]', "
            f"got: {header!r}"
        )
    type_raw = m.group(1)
    type_ = type_raw.lower()
    if type_ not in _VALID_TYPES:
        raise CompactParseError(
            f"Line {start_line}: unknown type {type_raw!r}. "
            f"Valid types: {sorted(_VALID_TYPES)}"
        )

    explicit_label = m.group(2).strip() if m.group(2) else None
    pb = _ParsedBlock(type_=type_, explicit_label=explicit_label, line_no=start_line)
    title_lines: list[str] = []
    current_list: list[str] | None = None
    title_done = False

    for offset, raw in enumerate(lines[1:], start=1):
        line_no = start_line + offset
        if not raw.strip():
            continue  # tolerate stray blank-ish lines inside a block

        item_m = _ITEM_RE.match(raw)
        if item_m:
            if current_list is None:
                raise CompactParseError(
                    f"Line {line_no}: list item with no preceding list key"
                )
            code = int(item_m.group(1))
            current_list.append((code, item_m.group(2).strip()))
            continue

        key_m = _KEY_RE.match(raw)
        if key_m:
            key = key_m.group(1).lower()
            value = key_m.group(2).strip()

            if key in _LIST_NAMES:
                if value:
                    raise CompactParseError(
                        f"Line {line_no}: list key {key!r} must be followed by "
                        f"indented '- item' lines, not inline value {value!r}"
                    )
                if key in pb.lists:
                    raise CompactParseError(
                        f"Line {line_no}: duplicate list key {key!r}"
                    )
                pb.lists[key] = []
                current_list = pb.lists[key]
            elif key in _KEY_NAMES:
                pb.keys[key] = value
                current_list = None
            else:
                pb.extra_keys[key] = value
                current_list = None
            title_done = True
            continue

        # Plain text: part of the title if we haven't seen a key/list yet
        if not title_done:
            title_lines.append(raw.strip())
        else:
            raise CompactParseError(
                f"Line {line_no}: unexpected text after keys/lists: {raw.strip()!r}"
            )

    pb.title = " ".join(title_lines).strip()
    return pb


def _parse_item_tags(raw: str) -> tuple[str, set[str]]:
    """Strip trailing [tag] markers from a list item's text body."""
    text = raw.strip()
    tags: set[str] = set()
    while True:
        m = _TRAILING_TAG_RE.search(text)
        if not m:
            break
        tags.add(m.group(1))
        text = text[: m.start()].rstrip()
    return text, tags


# ── Element builders ──────────────────────────────────────────────────────────


def _build_element(pb: _ParsedBlock, position: int) -> XmlElement:
    if pb.explicit_label:
        label = pb.explicit_label
        eid = f"doc:{label}"
    else:
        label = f"doc:q{position + 1}"
        eid = label

    builder = _BUILDERS.get(pb.type_)
    if builder is None:  # pragma: no cover — guarded by _VALID_TYPES
        raise CompactParseError(f"No builder for type {pb.type_!r}")
    return builder(pb, position, label, eid)


def _make_meta(pb: _ParsedBlock) -> ParserMeta:
    notes: list[str] = []
    if "note" in pb.keys:
        notes.append(pb.keys["note"])
    for k, v in pb.extra_keys.items():
        notes.append(f"unknown key {k!r}: {v!r}")
    term_note = _format_term_note(pb)
    if term_note:
        notes.append(term_note)
    return ParserMeta(
        source="doc",
        confidence=1.0,
        ambiguity_notes=notes,
        raw_display_logic=pb.keys.get("display"),
    )


def _format_term_note(pb: _ParsedBlock) -> str | None:
    """Validate and stringify the block-level `term:` expression.

    Accepts:
      - Bare coordinates: `r1`, `r1.c2`, `c3`
      - Comma-separated coordinate lists (implicit OR): `r1.c5, r2.c5`
      - Boolean compounds using `and` / `or` / `not` and parens:
        `r3 and r4`, `(r1 and r2) or r3`, `not r1`

    Validates only that every non-keyword/non-punctuation token is a
    well-formed coordinate. Does not enforce a parse tree — that's deferred
    until termination becomes a first-class model field (see O-8). The raw
    expression is stored verbatim in `parser_meta.ambiguity_notes`.
    """
    raw = pb.keys.get("term", "").strip()
    if not raw:
        return None
    for match in _TERM_TOKEN_RE.finditer(raw):
        tok = match.group(1)
        if tok in _TERM_PUNCT:
            continue
        if tok.lower() in _TERM_KEYWORDS:
            continue
        if _TERM_COORD_TOKEN_RE.match(tok):
            continue
        raise CompactParseError(
            f"Block at line {pb.line_no}: bad term token {tok!r}. "
            f"Allowed: coordinates ('rN', 'rN.cM', 'cN'), "
            f"'and' / 'or' / 'not', commas, parens."
        )
    return f"terminating condition (doc): {raw}"


def _is_optional(pb: _ParsedBlock) -> bool:
    flags = pb.keys.get("flags", "")
    return "optional" in {f.strip().lower() for f in flags.split(",") if f.strip()}


def _build_rows(pb: _ParsedBlock, parent_id: str) -> list[XmlRow]:
    raw_items = pb.lists.get("options") or pb.lists.get("rows") or []
    rows: list[XmlRow] = []
    for i, (code, raw) in enumerate(raw_items):
        text, tags = _parse_item_tags(raw)
        rows.append(
            XmlRow(
                label=f"r{i + 1}",
                value=code,
                text=text,
                text_raw=text,
                is_open="open" in tags,
                is_exclusive="exclusive" in tags,
                id=f"{parent_id}:r{i + 1}",
            )
        )
    return rows


def _build_cols(pb: _ParsedBlock, parent_id: str) -> list[XmlCol]:
    raw_items = pb.lists.get("cols", [])
    cols: list[XmlCol] = []
    for i, (_code, raw) in enumerate(raw_items):
        text, _ = _parse_item_tags(raw)
        cols.append(
            XmlCol(label=f"c{i + 1}", text=text, text_raw=text, id=f"{parent_id}:c{i + 1}")
        )
    return cols


def _build_choices(pb: _ParsedBlock, parent_id: str) -> list[XmlChoice]:
    raw_items = pb.lists.get("choices") or pb.lists.get("options") or []
    choices: list[XmlChoice] = []
    for i, (code, raw) in enumerate(raw_items):
        text, _ = _parse_item_tags(raw)
        choices.append(
            XmlChoice(
                label=f"c{i + 1}",
                value=code,
                text=text,
                text_raw=text,
                id=f"{parent_id}:c{i + 1}",
            )
        )
    return choices


def _build_radio(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlRadio:
    return XmlRadio(
        label=label, id=eid, position=position,
        title=pb.title, title_raw=pb.title,
        rows=_build_rows(pb, eid), cols=_build_cols(pb, eid),
        optional=_is_optional(pb),
        parser_meta=_make_meta(pb),
    )


def _build_checkbox(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlCheckbox:
    atleast = 1
    raw_atleast = pb.keys.get("atleast")
    if raw_atleast:
        try:
            atleast = int(raw_atleast)
        except ValueError:
            raise CompactParseError(
                f"Block at line {pb.line_no}: 'atleast' must be an integer, "
                f"got {raw_atleast!r}"
            )
    return XmlCheckbox(
        label=label, id=eid, position=position,
        title=pb.title, title_raw=pb.title,
        rows=_build_rows(pb, eid), cols=_build_cols(pb, eid), atleast=atleast,
        optional=_is_optional(pb),
        parser_meta=_make_meta(pb),
    )


def _build_text(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlText:
    rows = _build_rows(pb, eid)
    return XmlText(
        label=label, id=eid, position=position,
        title=pb.title, title_raw=pb.title,
        rows=rows, cols=_build_cols(pb, eid),
        is_grid=bool(rows),
        optional=_is_optional(pb),
        parser_meta=_make_meta(pb),
    )


def _build_number(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlNumber:
    return XmlNumber(
        label=label, id=eid, position=position,
        title=pb.title, title_raw=pb.title,
        optional=_is_optional(pb),
        parser_meta=_make_meta(pb),
    )


def _build_float(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlFloat:
    return XmlFloat(
        label=label, id=eid, position=position,
        title=pb.title, title_raw=pb.title,
        optional=_is_optional(pb),
        parser_meta=_make_meta(pb),
    )


def _build_select(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlSelect:
    return XmlSelect(
        label=label, id=eid, position=position,
        title=pb.title, title_raw=pb.title,
        choices=_build_choices(pb, eid),
        optional=_is_optional(pb),
        parser_meta=_make_meta(pb),
    )


def _build_html(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlHtml:
    return XmlHtml(
        label=label, id=eid, position=position,
        title=pb.title, title_raw=pb.title,
        parser_meta=_make_meta(pb),
    )


def _build_term(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlTerm:
    return XmlTerm(
        label=label, id=eid, position=position,
        cond=pb.keys.get("display", ""),
        text=pb.title,
    )


def _build_quota(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlQuota:
    return XmlQuota(
        label=label, id=eid, position=position,
        sheet=pb.keys.get("sheet", ""),
        overquota=pb.keys.get("overquota", "noqual"),
    )


def _build_goto(pb: _ParsedBlock, position: int, label: str, eid: str) -> XmlGoto:
    target = pb.keys.get("target")
    if not target:
        raise CompactParseError(
            f"Block at line {pb.line_no}: 'goto' requires a 'target:' key"
        )
    return XmlGoto(
        id=eid, position=position,
        target=target,
        cond=pb.keys.get("display"),
    )


_BUILDERS = {
    "radio": _build_radio,
    "checkbox": _build_checkbox,
    "text": _build_text,
    "number": _build_number,
    "float": _build_float,
    "select": _build_select,
    "html": _build_html,
    "term": _build_term,
    "quota": _build_quota,
    "goto": _build_goto,
}
