"""Heuristic text chunker for questionnaire documents.

Splits extracted text into "question blocks" — one block per question or
small group of questions — so the LLM can process them in focused batches.

For most surveys (< 50 questions, < 15 pages) the entire document fits in one
LLM call within gpt-4o-mini's 128k context. The chunker is only strictly
needed for very large instruments.

Design rules
------------
- A chunk boundary is identified when a line looks like a question start.
- Chunks are then grouped into batches of at most `max_questions_per_batch`
  so each LLM call is small and cheap.
- If no question-start pattern is found, the entire text is returned as one chunk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Matches common question-code patterns at the start of a line:
#   Q1.  Q2a.  S1.  D3b.  SC1.  P5.  F1.  T2.
#   Also bare codes like Q1 followed by whitespace and a capital letter.
_QUESTION_START_RE = re.compile(
    r"^\s*"
    r"(?:[A-Z]{1,3}\d+[a-z]?)"   # code: 1–3 capital letters + digits + optional suffix
    r"(?:[\.\)\:]|\s(?=[A-Z\"]))",  # delimiter: . ) : or space before capital/quote
    re.MULTILINE,
)

# How many characters constitute ~1 LLM token (rough estimate, conservative)
_CHARS_PER_TOKEN = 4

# Soft cap per batch before we start a new LLM call
MAX_TOKENS_PER_BATCH = 6_000
MAX_CHARS_PER_BATCH = MAX_TOKENS_PER_BATCH * _CHARS_PER_TOKEN


@dataclass
class TextChunk:
    """A contiguous slice of the questionnaire text."""

    text: str
    start_line: int  # 0-indexed line number where the chunk starts

    def __len__(self) -> int:
        return len(self.text)


def split_into_chunks(text: str) -> list[TextChunk]:
    """Split *text* into one chunk per identified question block.

    If no question-start patterns are found, a single chunk containing the
    full text is returned.
    """
    lines = text.splitlines(keepends=True)

    # Find line indices where a new question appears to start
    boundary_line_indices: list[int] = []
    for i, line in enumerate(lines):
        if _QUESTION_START_RE.match(line):
            boundary_line_indices.append(i)

    if not boundary_line_indices:
        # No structure detected — send everything as one chunk
        return [TextChunk(text=text, start_line=0)]

    # Build chunks between boundaries
    chunks: list[TextChunk] = []
    boundaries = boundary_line_indices + [len(lines)]  # sentinel

    for idx in range(len(boundary_line_indices)):
        start = boundaries[idx]
        end = boundaries[idx + 1]
        chunk_text = "".join(lines[start:end]).strip()
        if chunk_text:
            chunks.append(TextChunk(text=chunk_text, start_line=start))

    return chunks


def batch_chunks(chunks: list[TextChunk]) -> list[list[TextChunk]]:
    """Group chunks into batches that fit within the token budget.

    Each batch is sent as a single LLM call. Batches never split a single
    chunk across calls.
    """
    if not chunks:
        return []

    batches: list[list[TextChunk]] = []
    current_batch: list[TextChunk] = []
    current_chars = 0

    for chunk in chunks:
        chunk_chars = len(chunk)
        if current_batch and current_chars + chunk_chars > MAX_CHARS_PER_BATCH:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(chunk)
        current_chars += chunk_chars

    if current_batch:
        batches.append(current_batch)

    return batches
