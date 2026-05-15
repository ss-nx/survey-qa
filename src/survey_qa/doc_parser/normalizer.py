"""Label normalizer — align questionnaire labels to XML labels.

The questionnaire document may use different question codes than the Decipher
XML (e.g., the doc says "Q1" but the XML uses "Awareness_Q1").  This module
attempts to bridge that gap so the check layer can match them up.

Strategy (applied in order, stops at first match):
  1. Exact match             — Q1 == Q1
  2. Case-insensitive match  — q1 == Q1
  3. Strip common prefixes   — "question_Q1" → "Q1"
  4. Suffix match            — "Awareness_Q1" ends with "Q1"
  5. Fuzzy match (≥ threshold) — rapidfuzz token_sort_ratio

A NormalizationResult is returned for every questionnaire question,
indicating whether a match was found and how it was resolved.

Usage
-----
    from survey_qa.doc_parser.normalizer import normalize_labels

    result = normalize_labels(xml_labels, questionnaire_model)
    aligned_qm = result.aligned_model   # QuestionnaireModel with labels replaced
    for warning in result.warnings:
        print(warning)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ..core.models import ParsedQuestion, QuestionnaireModel

# Minimum fuzzy score to accept a match (0–100)
_FUZZY_THRESHOLD = 80.0

# Prefixes that are often stripped in questionnaire labels
_PREFIX_RE = re.compile(r"^(?:question_|q_|que_|item_)", re.IGNORECASE)


@dataclass
class NormalizationResult:
    aligned_model: QuestionnaireModel
    matched: dict[str, str]    # questionnaire_label → xml_label
    unmatched: list[str]       # questionnaire labels with no XML counterpart
    warnings: list[str]        # human-readable notes about fuzzy / suffix matches


def normalize_labels(
    xml_labels: set[str],
    questionnaire: QuestionnaireModel,
    fuzzy_threshold: float = _FUZZY_THRESHOLD,
) -> NormalizationResult:
    """Return a new QuestionnaireModel whose labels are remapped to *xml_labels*.

    Questions that cannot be matched are kept with their original labels so
    that Q-001 ("question not found in questionnaire") still fires correctly.
    """
    matched: dict[str, str] = {}
    unmatched: list[str] = []
    warnings: list[str] = []
    new_questions: list[ParsedQuestion] = []

    for q in questionnaire.questions:
        xml_label = _find_match(q.label, xml_labels, fuzzy_threshold, warnings)
        if xml_label is None:
            unmatched.append(q.label)
            new_questions.append(q)
        else:
            matched[q.label] = xml_label
            if xml_label != q.label:
                # Replace the label so checks can find it
                new_questions.append(q.model_copy(update={"label": xml_label}))
            else:
                new_questions.append(q)

    return NormalizationResult(
        aligned_model=QuestionnaireModel(questions=new_questions),
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

    # 3. Strip common prefix from questionnaire label, try again
    stripped = _PREFIX_RE.sub("", q_label)
    if stripped != q_label:
        if stripped in xml_labels:
            warnings.append(f"Prefix-strip match: '{q_label}' → '{stripped}'")
            return stripped
        if stripped.lower() in lower_map:
            matched = lower_map[stripped.lower()]
            warnings.append(f"Prefix-strip + case match: '{q_label}' → '{matched}'")
            return matched

    # 4. Suffix match — XML label ends with questionnaire label (or vice versa)
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
