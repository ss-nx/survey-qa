"""Write a color-coded Excel QA report.

Usage:
    python make_report.py <xml_path> <findings_json_path> <output.xlsx>

Findings JSON should be the `findings` array (or the full output) from run_checks.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from pydantic import ValidationError

from survey_qa.core.models import Finding
from survey_qa.reporters.excel import write_report
from survey_qa.xml_parser import parse as parse_xml


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: make_report.py <xml_path> <findings_json_path> <output.xlsx>", file=sys.stderr)
        return 2

    xml_path = Path(argv[0]).expanduser()
    findings_path = Path(argv[1]).expanduser()
    out_path = Path(argv[2]).expanduser()

    for p, name in [(xml_path, "XML"), (findings_path, "findings JSON")]:
        if not p.exists():
            print(f"error: {name} file not found: {p}", file=sys.stderr)
            return 1

    try:
        payload = json.loads(findings_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"error: findings JSON is malformed: {exc}", file=sys.stderr)
        return 1

    # Accept either the full run_checks output or just a list of findings
    raw_findings = payload["findings"] if isinstance(payload, dict) else payload

    try:
        findings = [Finding.model_validate(f) for f in raw_findings]
    except ValidationError as exc:
        print(f"error: findings did not validate: {exc}", file=sys.stderr)
        return 1

    try:
        survey = parse_xml(xml_path)
    except Exception as exc:
        print(f"error: XML parse failed: {exc}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(out_path, survey, findings)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
