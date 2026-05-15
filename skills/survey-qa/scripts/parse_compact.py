"""Parse a compact-format doc file and print the SurveyModel as JSON to stdout.

Usage:
    python parse_compact.py <path/to/doc.compact.txt>
    python parse_compact.py -                       # read from stdin
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401 — adds skill root to sys.path

from survey_qa.doc_parser.compact_parser import CompactParseError, parse_compact


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: parse_compact.py <compact_path> | -", file=sys.stderr)
        return 2

    if argv[0] == "-":
        text = sys.stdin.read()
    else:
        compact_path = Path(argv[0]).expanduser()
        if not compact_path.exists():
            print(f"error: file not found: {compact_path}", file=sys.stderr)
            return 1
        text = compact_path.read_text(encoding="utf-8")

    try:
        survey = parse_compact(text)
    except CompactParseError as exc:
        print(f"error: compact parse failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(survey.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
