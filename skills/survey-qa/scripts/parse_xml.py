"""Parse a Decipher XML file and print the SurveyModel as JSON to stdout.

Usage:
    python parse_xml.py <path/to/survey.xml>
    python parse_xml.py --schema-only          # print JSON Schema of SurveyModel
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401 — adds skill root to sys.path

from survey_qa.core.models import SurveyModel
from survey_qa.xml_parser import parse


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: parse_xml.py <xml_path> | --schema-only", file=sys.stderr)
        return 2

    if argv[0] == "--schema-only":
        print(json.dumps(SurveyModel.model_json_schema(), indent=2))
        return 0

    xml_path = Path(argv[0]).expanduser()
    if not xml_path.exists():
        print(f"error: file not found: {xml_path}", file=sys.stderr)
        return 1

    try:
        survey = parse(xml_path)
    except Exception as exc:
        print(f"error: XML parse failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(survey.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
