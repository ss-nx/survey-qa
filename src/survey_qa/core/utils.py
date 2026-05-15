"""Shared utilities: HTML stripping, fuzzy text matching."""

from __future__ import annotations

import html
import re

from rapidfuzz import fuzz


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(raw: str | None) -> str:
    """Strip HTML tags, decode entities, and normalise whitespace.

    >>> strip_html("<strong>Hello &amp; world</strong>")
    'Hello & world'
    >>> strip_html(None)
    ''
    """
    if not raw:
        return ""
    decoded = html.unescape(raw)
    no_tags = _TAG_RE.sub(" ", decoded)
    return _WHITESPACE_RE.sub(" ", no_tags).strip()


def fuzzy_match(a: str, b: str) -> float:
    """Return a 0–100 similarity score between two strings (token sort ratio).

    Token sort ratio handles minor word-order differences and is more robust
    than simple ratio for survey question text.
    """
    return fuzz.token_sort_ratio(a.lower(), b.lower())


def texts_match(a: str, b: str, threshold: float = 90.0) -> bool:
    """Return True when two strings are similar enough to be considered equal."""
    return fuzzy_match(a, b) >= threshold
