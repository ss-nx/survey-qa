"""Run all 26 QA checks comparing an XML survey to a doc-side SurveyModel.

Usage:
    python run_checks.py <xml_path> <doc_survey_json_path>

The doc_survey JSON file must conform to SurveyModel. Run
`parse_xml.py --schema-only` to see the schema.

Prints a JSON object with `findings`, `summary`, `normalization_warnings`,
and `unmatched_labels` to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from pydantic import ValidationError

from survey_qa.checks import run_checks
from survey_qa.checks.routing_checks import run_routing_checks
from survey_qa.core.models import SurveyModel
from survey_qa.doc_parser.normalizer import normalize_labels
from survey_qa.xml_parser import parse as parse_xml


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: run_checks.py <xml_path> <doc_survey_json_path>", file=sys.stderr)
        return 2

    xml_path = Path(argv[0]).expanduser()
    doc_json_path = Path(argv[1]).expanduser()

    for p, name in [(xml_path, "XML"), (doc_json_path, "doc_survey JSON")]:
        if not p.exists():
            print(f"error: {name} file not found: {p}", file=sys.stderr)
            return 1

    try:
        doc_payload = json.loads(doc_json_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"error: doc_survey JSON is malformed: {exc}", file=sys.stderr)
        return 1

    try:
        doc_model = SurveyModel.model_validate(doc_payload)
    except ValidationError as exc:
        print(
            json.dumps(
                {
                    "error": "doc_survey did not validate against SurveyModel",
                    "validation_errors": exc.errors(),
                },
                indent=2,
            )
        )
        return 1

    try:
        xml_model = parse_xml(xml_path)
    except Exception as exc:
        print(f"error: XML parse failed: {exc}", file=sys.stderr)
        return 1

    norm = normalize_labels(xml_model, doc_model)
    doc_aligned = norm.aligned_model

    findings = run_checks(xml_model, doc_aligned) + run_routing_checks(xml_model, doc_aligned)

    output = {
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

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
