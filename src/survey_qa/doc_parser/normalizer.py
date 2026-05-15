"""Label normalizer — align doc-side labels to XML-side labels.

The questionnaire document may use different question codes than the Decipher
XML (e.g., the doc says "Q1" but the XML uses "Awareness_Q1"). This module
bridges that gap so the check layer can match elements up by label.

Strategy (applied in order, stops at first match):
  1. Exact match             — Q1 == Q1
  2. Case-insensitive match  — q1 == Q1
  3. Strip common prefixes   — "question_Q1" → "Q1"
  4. Suffix match            — "Awareness_Q1" ends with "Q1"
  5. Fuzzy match (≥ threshold) — rapidfuzz token_sort_ratio

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

from ..core.models import SurveyModel, XmlElement

# Minimum fuzzy score to accept a match (0–100)
_FUZZY_THRESHOLD = 80.0

# Prefixes that are often stripped in questionnaire labels
_PREFIX_RE = re.compile(r"^(?:question_|q_|que_|item_)", re.IGNORECASE)


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
) -> NormalizationResult:
    """Return a new doc-side SurveyModel whose labels are remapped to *xml* labels.

    Elements that cannot be matched are kept with their original labels so
    that Q-001 ("question not found in questionnaire") still fires correctly.
    """
    xml_labels = xml.labels()

    matched: dict[str, str] = {}
    unmatched: list[str] = []
    warnings: list[str] = []
    new_elements: list[XmlElement] = []

    for e in doc.elements:
        original_label = getattr(e, "label", None)
        if original_label is None:
            new_elements.append(e)
            continue

        xml_label = _find_match(original_label, xml_labels, fuzzy_threshold, warnings)
        if xml_label is None:
            unmatched.append(original_label)
            new_elements.append(e)
        else:
            matched[original_label] = xml_label
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
