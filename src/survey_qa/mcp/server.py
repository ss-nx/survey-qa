"""FastMCP server for survey-qa.

Compares a Forsta Decipher XML survey against a client questionnaire (Word
or PDF) using a deterministic Python pipeline plus Claude's reading of the
questionnaire authored in the compact format. Designed for distribution as
an MCPB bundle so Claude Desktop's bundled `uv` handles Python/deps
automatically across macOS, Linux, and Windows.

Workflow Claude follows when invoked
------------------------------------
  1. `parse_xml(xml_path)`                         → XML-side SurveyModel
  2. `extract_doc_text(doc_path)`                  → text + <b>/<i>/<u> tags
  3. Claude reads that text and authors a compact-format string covering
     every question, applying the rules returned by `get_workflow_guide()`.
  4. `check_survey(xml_path, doc_compact)`         → findings + summary
  5. Optionally `generate_report(...)`             → Excel report

`get_workflow_guide()` returns the compact-format spec — Claude calls it
once at the start of a QA session if the format isn't already in context.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..checks import registered_checks
from ..checks import run_checks as _run_checks
from ..checks.routing_checks import run_routing_checks
from ..core.models import Finding, SurveyModel
from ..doc_parser.compact_parser import CompactParseError, parse_compact
from ..doc_parser.extractor import extract_docx, extract_pdf
from ..doc_parser.normalizer import normalize_labels
from ..reporters.excel import write_report
from ..xml_parser import parse as parse_xml_file

log = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "MCP server requires the 'mcp' extra. Install with: pip install -e '.[mcp]'"
    ) from exc


mcp = FastMCP("survey-qa")


_WORKFLOW_GUIDE = """\
# survey-qa compact format — authoring guide

You are running a survey QA workflow. The user has a Decipher XML survey
script and a questionnaire document (Word or PDF). Your job is to compare
them and surface every place the XML doesn't match the questionnaire.

## Primary workflow (2 tool calls)

  1. `extract_doc_text(doc_path)`
     Returns the questionnaire text with inline formatting preserved as
     <b>/<i>/<u> tags. Read it carefully and author a compact-format string
     covering every survey element (rules below).

  2. `run_qa(xml_path, doc_compact, output_path?)`
     Parses the XML, runs all QA checks, optionally writes an Excel report.
     Returns findings, summary counts, and normalization warnings.

Use `parse_xml`, `check_survey`, and `generate_report` individually only when
you need to inspect or re-run a specific step.

## Compact format — one block per survey element

```
## <type>
<title text>
<key>: <value>
options:
  1. <option text>  [tag] [tag]
  2. <option text>
```

- Header: `## <type>` or `## <type> [label]`. Recognized types: radio,
  checkbox, text, number, float, select, html, term, quota, goto.
  Use `[label]` when the questionnaire labels the question (e.g.
  `## radio [S1]`); omit when it doesn't (parser auto-binds via title
  similarity).
- Title: free text on the line(s) below the header.
- Keys: flags, atleast, display, options, choices, rows, cols, target,
  sheet, overquota, term, note. Emit only when the default differs.

## Always-numbered options

Every list item is `N. text`. The number is the option's `value`. If the
questionnaire shows codes (e.g. `99. Refused`), copy them verbatim;
otherwise number sequentially `1..N`. Applies to `options:`, `rows:`,
`cols:`, `choices:`.

## Row tags

- `[open]`   — "Other, please specify" type rows
- `[exclusive]` — "None of the above" / "Prefer not to say"

## Termination

Block-level `term:` expresses screen-out conditions using coordinates and
boolean operators:
- Coordinates: `rN`, `rN.cM`, `cN`
- Operators: `and`, `or`, `not`, parens
- Comma is shorthand for OR
- Examples: `term: r4`, `term: r1.c5, r2.c5`, `term: r3 and r4`,
  `term: (r1 and r2) or r3`

## Text formatting & structure

Preserve formatting from the doc using HTML tags (matches XML side):
- Bold `<b>...</b>`, italic `<i>...</i>`, underline `<u>...</u>`
- Visible line break `<br>`
- Inline list `<ul><li>...</li></ul>` (or `<ol>`)
- Ignore color

## Example blocks

```
## radio [S1]
Where do you live?
options:
  1. United States
  2. Canada
  3. United Kingdom
  98. Other, please specify  [open]
  99. I prefer not to answer  [exclusive]

## checkbox [S4]
Select <b>all</b> that apply.
atleast: 1
options:
  1. Netflix
  2. Hulu
  3. Disney+
  99. None of the above  [exclusive]

## radio [S2]
What is your age?
term: r4
options:
  1. 18-24
  2. 25-34
  3. 35-44
  4. Under 18
```

## Important rules

- The questionnaire is the source of truth. Phrase findings as "XML should
  match the questionnaire."
- Don't invent content, labels, or codes the doc doesn't show.
- Don't paraphrase — copy text verbatim including punctuation.
- One option per compact-format line; use `<br>` for intentional in-option
  line breaks.
- For ambiguous content, add a `note:` line — it surfaces in the report.
"""


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_workflow_guide() -> str:
    """Return the survey-qa workflow + compact-format authoring guide.

    Call this once at the start of a QA session if you're unfamiliar with
    the compact format. The guide explains every block type, the tag set,
    formatting conventions, and termination syntax.
    """
    return _WORKFLOW_GUIDE


@mcp.tool()
def parse_xml(file_path: str) -> dict[str, Any]:
    """Parse a Decipher XML survey file into a SurveyModel (deterministic, no LLM).

    Args:
        file_path: Path to the .xml file.

    Returns:
        Serialized SurveyModel — survey_label, elements (questions, terms,
        quotas, gotos, suspends, in document order), or {"error": ...}.
    """
    path = Path(file_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    try:
        survey = parse_xml_file(path)
    except Exception as exc:
        return {"error": f"XML parse failed: {exc}"}
    return survey.model_dump()


@mcp.tool()
def extract_doc_text(file_path: str) -> dict[str, Any]:
    """Extract plain text from a .docx or .pdf, preserving inline formatting.

    Bold, italic, and underline runs are emitted as `<b>`, `<i>`, `<u>` HTML
    tags so they survive into the compact format you'll author and match the
    XML side's inline markup. Color is intentionally not preserved.

    Args:
        file_path: Path to the .docx or .pdf file.

    Returns:
        {"text": "..."} with the extracted content, or {"error": ...}.
    """
    path = Path(file_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            text = extract_docx(path)
        elif suffix == ".pdf":
            text = extract_pdf(path)
        else:
            return {"error": f"Unsupported extension: {suffix!r} (expected .docx or .pdf)"}
    except Exception as exc:
        return {"error": f"Extraction failed: {exc}"}
    return {"text": text}


@mcp.tool()
def check_survey(xml_path: str, doc_compact: str) -> dict[str, Any]:
    """Parse the compact-format doc, run all QA checks, return findings.

    Steps internally: compact-format → SurveyModel → label normalization
    (exact / fuzzy / title-similarity) → question + routing checks.

    Args:
        xml_path: Path to the Decipher XML survey.
        doc_compact: Compact-format string you authored from the
            questionnaire. See `get_workflow_guide()` for the format spec.

    Returns:
        {
          "findings": [...],
          "summary": {errors, warnings, infos, total},
          "normalization_warnings": [...],
          "unmatched_labels": [...]
        }
        or {"error": ...} for malformed inputs.
    """
    xml_path_obj = Path(xml_path).expanduser()
    if not xml_path_obj.exists():
        return {"error": f"XML file not found: {xml_path}"}

    try:
        doc_model = parse_compact(doc_compact)
    except CompactParseError as exc:
        return {"error": f"Compact-format parse failed: {exc}"}

    try:
        xml_model = parse_xml_file(xml_path_obj)
    except Exception as exc:
        return {"error": f"XML parse failed: {exc}"}

    norm = normalize_labels(xml_model, doc_model)
    doc_aligned = norm.aligned_model

    findings: list[Finding] = (
        _run_checks(xml_model, doc_aligned)
        + run_routing_checks(xml_model, doc_aligned)
    )

    return {
        "findings": [f.model_dump() for f in findings],
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "infos": sum(1 for f in findings if f.severity == "info"),
            "total": len(findings),
        },
        "normalization_warnings": norm.warnings,
        "unmatched_labels": norm.unmatched,
    }


@mcp.tool()
def run_qa(
    xml_path: str,
    doc_compact: str,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Parse compact-format doc, run all QA checks, optionally write Excel report.

    This is the single call for the primary workflow — it combines check_survey
    and generate_report into one step.

    Args:
        xml_path:     Path to the Decipher XML survey.
        doc_compact:  Compact-format string you authored from the questionnaire.
                      See get_workflow_guide() for the format spec.
        output_path:  Optional path for the Excel report (.xlsx). When provided
                      the report is written and its path is included in the
                      response. Omit if you only need the findings JSON.

    Returns:
        {
          "findings": [...],
          "summary": {errors, warnings, infos, total},
          "normalization_warnings": [...],
          "unmatched_labels": [...],
          "report_path": "/abs/path/to/report.xlsx"  # only when output_path given
        }
        or {"error": ...} for malformed inputs.
    """
    xml_path_obj = Path(xml_path).expanduser()
    if not xml_path_obj.exists():
        return {"error": f"XML file not found: {xml_path}"}

    try:
        doc_model = parse_compact(doc_compact)
    except CompactParseError as exc:
        return {"error": f"Compact-format parse failed: {exc}"}

    try:
        xml_model = parse_xml_file(xml_path_obj)
    except Exception as exc:
        return {"error": f"XML parse failed: {exc}"}

    norm = normalize_labels(xml_model, doc_model)
    doc_aligned = norm.aligned_model

    findings: list[Finding] = (
        _run_checks(xml_model, doc_aligned)
        + run_routing_checks(xml_model, doc_aligned)
    )

    result: dict[str, Any] = {
        "findings": [f.model_dump() for f in findings],
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "infos": sum(1 for f in findings if f.severity == "info"),
            "total": len(findings),
        },
        "normalization_warnings": norm.warnings,
        "unmatched_labels": norm.unmatched,
    }

    if output_path:
        out = Path(output_path).expanduser().resolve()
        try:
            write_report(out, xml_model, findings)
            result["report_path"] = str(out)
        except Exception as exc:
            result["report_error"] = f"Report generation failed: {exc}"

    return result


@mcp.tool()
def list_checks() -> list[dict[str, str]]:
    """List all registered QA checks (id + description)."""
    from ..checks import (  # noqa: F401 — side-effect import registers checks
        checkbox_checks,
        question_checks,
        radio_checks,
        routing_checks,
        select_checks,
        text_checks,
    )
    return [
        {
            "id": cls.id,
            "description": getattr(cls, "description", cls.__doc__ or ""),
        }
        for cls in registered_checks()
    ]


@mcp.tool()
def generate_report(
    xml_path: str,
    findings: list[dict[str, Any]],
    output_path: str,
) -> dict[str, Any]:
    """Write a color-coded Excel QA report (Summary / Findings / Questions).

    Args:
        xml_path: Path to the XML survey (used to populate the Questions sheet).
        findings: Findings list (typically straight from check_survey()).
        output_path: Where to write the .xlsx file.

    Returns:
        {"path": "/abs/path/to/output.xlsx"} or {"error": ...}.
    """
    xml_path_obj = Path(xml_path).expanduser()
    out = Path(output_path).expanduser().resolve()

    if not xml_path_obj.exists():
        return {"error": f"XML file not found: {xml_path}"}

    try:
        finding_models = [Finding.model_validate(f) for f in findings]
    except ValidationError as exc:
        return {
            "error": "Findings did not validate",
            "validation_errors": exc.errors(),
        }

    try:
        xml_model = parse_xml_file(xml_path_obj)
        write_report(out, xml_model, finding_models)
    except Exception as exc:
        return {"error": f"Report generation failed: {exc}"}

    return {"path": str(out)}


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server on stdio. Used as the survey-qa-mcp console script."""
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
