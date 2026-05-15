"""Extract plain text from a .docx or .pdf and print it to stdout.

Usage:
    python extract_doc_text.py <path/to/questionnaire.docx>
    python extract_doc_text.py <path/to/questionnaire.pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from survey_qa.doc_parser.extractor import extract_docx, extract_pdf


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: extract_doc_text.py <path>", file=sys.stderr)
        return 2

    path = Path(argv[0]).expanduser()
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            text = extract_docx(path)
        elif suffix == ".pdf":
            text = extract_pdf(path)
        else:
            print(f"error: unsupported extension: {suffix!r}", file=sys.stderr)
            return 1
    except Exception as exc:
        print(f"error: extraction failed: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
