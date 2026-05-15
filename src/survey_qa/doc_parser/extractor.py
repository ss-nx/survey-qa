"""Raw text extraction from Word and PDF documents.

Stage 1 of the two-stage parsing pipeline. No LLM involved.
Output is a plain string preserving paragraph / line structure.
"""

from __future__ import annotations

from pathlib import Path


def extract_docx(path: Path) -> str:
    """Extract text from a .docx file, preserving paragraph line breaks.

    Bold/italic formatting is lost, but paragraph order and whitespace
    structure is preserved — enough for the chunker and LLM to work with.
    """
    import docx  # python-docx

    document = docx.Document(str(path))
    lines: list[str] = []

    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            lines.append(text)
        else:
            # Keep blank lines so chunker can use them as boundaries
            lines.append("")

    # Also pull text from tables (e.g., grid questions, quota specs)
    for table in document.tables:
        lines.append("")
        for row in table.rows:
            cell_texts = [cell.text.strip() for cell in row.cells]
            lines.append("\t".join(cell_texts))
        lines.append("")

    return "\n".join(lines)


def extract_pdf(path: Path) -> str:
    """Extract text from a PDF file, page by page.

    pdfplumber preserves approximate column layout. Pages are joined
    with a form-feed marker so the chunker can treat them as boundaries.
    """
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                pages.append(text.strip())

    return "\n\f\n".join(pages)
