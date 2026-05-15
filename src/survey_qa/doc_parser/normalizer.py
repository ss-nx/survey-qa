"""Label normalizer — align doc-side labels to XML-side labels.

The questionnaire document may use different question codes than the Decipher
XML (e.g., the doc says "Q1" but the XML uses "Awareness_Q1"). This module
bridges that gap so the check layer can match elements up by label.

Strategy (applied in order, stops at first match):
  1. Exact match             — Q1 == Q1
  2. Case-insensitive match  — q1 == Q1
  3. Strip common prefixes   — "question_Q1" → "Q1"
  4. Suffix match            — "Awareness_Q1" ends with "Q1"
  5. Fuzzy label match (≥ threshold) — rapidfuzz token_sort_ratio
  6. Title-similarity match  — applies when doc-side labels are synthetic
                                (e.g., 'doc:q1' from the compact parser).
                                Compares question titles, requires same tag,
                                won't reuse an XML question already matched.

A NormalizationResult is returned for every doc-side element, indicating
whether a match was found and how it was resolved.

Usage
-----
    from survey_qa.doc_parser.normalizer import normalize_labels

    result = normalize_labels(xml_model, doc_model)
    aligned_doc = result.aligned_model   # SurveyModel with labels replaced
    for warning in result.warnings:
        print(warning)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..core.models import SurveyModel, XmlElement, XmlQuestion

# Minimum fuzzy score to accept a label match (0–100)
_FUZZY_THRESHOLD = 80.0

# Minimum title-similarity score to accept a title-based match (0–100)
_TITLE_THRESHOLD = 80.0

# Tolerance band for title-score ties — within this many points of the best
# match, prefer the XML question earliest in document order.
_TITLE_TIE_MARGIN = 5.0

# Prefixes that are often stripped in questionnaire labels
_PREFIX_RE = re.compile(r"^(?:question_|q_|que_|item_)", re.IGNORECASE)

# Synthetic-label sentinel used by the compact parser (doc-side). Labels with
# this prefix are placeholders and should bind via title similarity, not by
# coincidental suffix/fuzzy overlap with XML codes.
_SYNTHETIC_LABEL_PREFIX = "doc:"


@dataclass
class NormalizationResult:
    aligned_model: SurveyModel
    matched: dict[str, str]    # doc_label → xml_label
    unmatched: list[str]       # doc labels with no XML counterpart
    warnings: list[str]        # human-readable notes about fuzzy / suffix matches


def normalize_labels(
    xml: SurveyModel,
    doc: SurveyModel,
    fuzzy_threshold: float = _FUZZY_THRESHOLD,
    title_threshold: float = _TITLE_THRESHOLD,
    title_tie_margin: float = _TITLE_TIE_MARGIN,
) -> NormalizationResult:
    """Return a new doc-side SurveyModel whose labels are remapped to *xml* labels.

    Elements that cannot be matched are kept with their original labels so
    that Q-001 ("question not found in questionnaire") still fires correctly.
    """
    xml_labels = xml.labels()
    xml_questions_by_label: dict[str, XmlQuestion] = {q.label: q for q in xml.questions()}

    matched: dict[str, str] = {}
    unmatched: list[str] = []
    warnings: list[str] = []
    new_elements: list[XmlElement] = []
    matched_xml_labels: set[str] = set()

    for e in doc.elements:
        original_label = getattr(e, "label", None)
        if original_label is None:
            new_elements.append(e)
            continue

        if original_label.startswith(_SYNTHETIC_LABEL_PREFIX):
            xml_label = None  # synthetic; skip label strategies, go to title
        else:
            xml_label = _find_match(original_label, xml_labels, fuzzy_threshold, warnings)

        if xml_label is None and isinstance(e, XmlQuestion) and e.title:
            xml_label = _find_title_match(
                e,
                xml_questions_by_label,
                matched_xml_labels,
                title_threshold,
                title_tie_margin,
                warnings,
            )

        if xml_label is None:
            unmatched.append(original_label)
            new_elements.append(e)
        else:
            matched[original_label] = xml_label
            matched_xml_labels.add(xml_label)
            if xml_label != original_label:
                new_elements.append(e.model_copy(update={"label": xml_label}))
            else:
                new_elements.append(e)

    return NormalizationResult(
        aligned_model=SurveyModel(survey_label=doc.survey_label, elements=new_elements),
        matched=matched,
        unmatched=unmatched,
        warnings=warnings,
    )


def _find_match(
    q_label: str,
    xml_labels: set[str],
    threshold: float,
    warnings: list[str],
) -> str | None:
    # 1. Exact
    if q_label in xml_labels:
        return q_label

    # 2. Case-insensitive
    lower_map = {x.lower(): x for x in xml_labels}
    if q_label.lower() in lower_map:
        matched = lower_map[q_label.lower()]
        warnings.append(f"Case-insensitive match: '{q_label}' → '{matched}'")
        return matched

    # 3. Strip common prefix from doc label, try again
    stripped = _PREFIX_RE.sub("", q_label)
    if stripped != q_label:
        if stripped in xml_labels:
            warnings.append(f"Prefix-strip match: '{q_label}' → '{stripped}'")
            return stripped
        if stripped.lower() in lower_map:
            matched = lower_map[stripped.lower()]
            warnings.append(f"Prefix-strip + case match: '{q_label}' → '{matched}'")
            return matched

    # 4. Suffix match — XML label ends with doc label (or vice versa)
    for xml_label in xml_labels:
        if xml_label.endswith(q_label) or xml_label.lower().endswith(q_label.lower()):
            warnings.append(f"Suffix match: '{q_label}' → '{xml_label}'")
            return xml_label
        if q_label.endswith(xml_label) or q_label.lower().endswith(xml_label.lower()):
            warnings.append(f"Suffix match (reversed): '{q_label}' → '{xml_label}'")
            return xml_label

    # 5. Fuzzy
    best_score = 0.0
    best_label: str | None = None
    for xml_label in xml_labels:
        score = fuzz.token_sort_ratio(q_label.lower(), xml_label.lower())
        if score > best_score:
            best_score = score
            best_label = xml_label

    if best_label is not None and best_score >= threshold:
        warnings.append(
            f"Fuzzy match ({best_score:.0f}%): '{q_label}' → '{best_label}'"
        )
        return best_label

    return None


def _find_title_match(
    doc_q: XmlQuestion,
    xml_questions_by_label: dict[str, XmlQuestion],
    matched_xml_labels: set[str],
    threshold: float,
    tie_margin: float,
    warnings: list[str],
) -> str | None:
    """Match a doc-side question to an XML question by title similarity.

    Constraints:
      - same `tag` (radio ↔ radio, etc.)
      - similarity score ≥ `threshold`
      - XML question not already matched to an earlier doc-side question
      - on ties within `tie_margin` points, prefer the XML question earliest
        in document order
    """
    doc_title = doc_q.title.strip().lower()
    if not doc_title:
        return None

    candidates: list[tuple[float, int, str]] = []  # (score, xml_position, xml_label)
    for xml_label, xml_q in xml_questions_by_label.items():
        if xml_label in matched_xml_labels:
            continue
        if xml_q.tag != doc_q.tag:
            continue
        xml_title = (xml_q.title or "").strip().lower()
        if not xml_title:
            continue
        score = fuzz.token_sort_ratio(doc_title, xml_title)
        if score >= threshold:
            candidates.append((score, xml_q.position, xml_label))

    if not candidates:
        return None

    candidates.sort(key=lambda t: (-t[0], t[1]))
    best_score = candidates[0][0]
    ties = [c for c in candidates if best_score - c[0] <= tie_margin]
    chosen = min(ties, key=lambda t: t[1])  # earliest doc-order

    warnings.append(
        f"Title-similarity match ({chosen[0]:.0f}%): "
        f"{doc_q.title!r} → XML label {chosen[2]!r}"
    )
    return chosen[2]
