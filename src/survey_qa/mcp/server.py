"""FastMCP server for survey-qa.

Tools exposed:
- get_survey_model_schema()           → JSON Schema for SurveyModel
- parse_xml(file_path)                → SurveyModel (XML side, deterministic)
- run_checks(xml_path, doc_survey)    → findings + summary
- list_checks()                       → registered checks
- generate_report(xml_path, findings, output_path) → Excel path

In MCP mode Claude is the doc parser. It reads the questionnaire from the
conversation, constructs SurveyModel-shaped JSON (the same shape `parse_xml`
returns), and passes it as `doc_survey`. Pydantic validates on receipt.
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
from ..doc_parser.normalizer import normalize_labels
from ..reporters.excel import write_report
from ..xml_parser import parse as parse_xml_file

log = logging.getLogger(__name__)

# Import FastMCP lazily so the package imports cleanly without the mcp extra
try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "MCP server requires the 'mcp' extra. Install with: pip install -e '.[mcp]'"
    ) from exc


mcp = FastMCP("survey-qa")


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_survey_model_schema() -> dict[str, Any]:
    """Return the JSON Schema for SurveyModel.

    Use this when constructing the `doc_survey` argument for `run_checks` —
    your data must conform to this schema. SurveyModel.elements is a
    discriminated union by `tag` field: each element must have a `tag` of
    'radio' | 'checkbox' | 'text' | 'number' | 'float' | 'select' | 'html' |
    'rating' | 'rank' | 'ranksort' | 'term' | 'quota' | 'goto' | 'suspend'.
    """
    return SurveyModel.model_json_schema()


@mcp.tool()
def parse_xml(file_path: str) -> dict[str, Any]:
    """Parse a Decipher XML survey file into a SurveyModel (no LLM).

    Args:
        file_path: Path to the .xml file.

    Returns:
        Serialized SurveyModel — survey_label, elements (questions, terms,
        quotas, gotos, suspends, in document order).
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
def run_checks(xml_path: str, doc_survey: dict[str, Any]) -> dict[str, Any]:
    """Run all QA checks comparing an XML survey against a doc-side SurveyModel.

    The doc_survey argument is constructed by you (Claude) from the
    questionnaire document. Its shape must match SurveyModel — call
    `get_survey_model_schema()` first if unsure. Pydantic validates on receipt;
    a validation failure returns an error response with details.

    For each respondent-facing question type, populate the matching
    XmlElement variant:
      - radio    → tag='radio', label, title, rows[]
      - checkbox → tag='checkbox', label, title, rows[], atleast
      - text     → tag='text', label, title
      - select   → tag='select', label, title, choices[]
      - number / float / html / rating → similar minimal shape

    Each row needs: label, text, text_raw, id (use synthetic IDs like
    "doc:Q1:r1" — they only need to be unique within the doc-side model).

    If a field isn't extractable from the document, leave it at its default
    (None / empty list). Checks handle missing doc-side data gracefully.

    Args:
        xml_path: Path to the Decipher XML survey file.
        doc_survey: SurveyModel-shaped JSON representing the questionnaire.

    Returns:
        Dict with `findings` (list of Finding objects) and `summary` (counts
        of errors / warnings / infos), or `error` if validation fails.
    """
    xml_path_obj = Path(xml_path).expanduser()
    if not xml_path_obj.exists():
        return {"error": f"XML file not found: {xml_path}"}

    try:
        doc_model = SurveyModel.model_validate(doc_survey)
    except ValidationError as exc:
        return {
            "error": "doc_survey did not validate against SurveyModel",
            "validation_errors": exc.errors(),
        }

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
def list_checks() -> list[dict[str, str]]:
    """List all registered QA checks (id + description)."""
    # Side-effect imports register the check classes
    from ..checks import (  # noqa: F401
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
        findings: List of Finding-shaped dicts (typically from run_checks).
        output_path: Where to write the .xlsx file.

    Returns:
        Dict with `path` (absolute path written) or `error`.
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
