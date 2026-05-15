"""Routing QA checks (RO-001 through RO-005).

Routing checks operate differently from question-level checks:
they receive the full XML and doc SurveyModels, not a single question pair.
They are invoked separately via run_routing_checks().
"""

from __future__ import annotations

import re

from ..core.models import Finding, SurveyModel, XmlQuestion, XmlSuspend


_LABEL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")


def run_routing_checks(xml: SurveyModel, doc: SurveyModel) -> list[Finding]:
    """Run all routing checks and return findings."""
    findings: list[Finding] = []
    findings.extend(_ro001_term_labels(xml, doc))
    findings.extend(_ro002_term_cond_labels(xml))
    findings.extend(_ro003_goto_targets(xml))
    findings.extend(_ro004_suspend_after_questions(xml))
    findings.extend(_ro005_cond_has_routing_note(xml, doc))
    return findings


def _doc_routing_text(doc: SurveyModel) -> set[str]:
    """Collect all labels mentioned in any doc-side raw display logic."""
    labels: set[str] = set()
    for q in doc.questions():
        meta = q.parser_meta
        if meta is None or not meta.raw_display_logic:
            continue
        labels.update(_LABEL_RE.findall(meta.raw_display_logic))
    return labels


def _ro001_term_labels(xml: SurveyModel, doc: SurveyModel) -> list[Finding]:
    """RO-001: Every <term> label matches an expected terminate in the questionnaire."""
    findings = []
    doc_routing_labels = _doc_routing_text(doc)

    for term in xml.terms():
        if doc_routing_labels and term.label not in doc_routing_labels:
            findings.append(
                Finding(
                    check_id="RO-001",
                    severity="warning",
                    question_label=term.label,
                    message=f"Term '{term.label}' (cond: {term.cond!r}) not referenced in questionnaire routing rules",
                )
            )
    return findings


def _ro002_term_cond_labels(xml: SurveyModel) -> list[Finding]:
    """RO-002: <term> condition references question labels that exist in the survey."""
    findings = []
    known_labels = xml.labels()

    for term in xml.terms():
        cond = term.cond
        if not cond:
            continue
        referenced = _LABEL_RE.findall(cond)
        python_keywords = {
            "and", "or", "not", "in", "is", "if", "else", "True", "False",
            "None", "ans", "hasMarker", "gv", "p", "any", "all",
        }
        for ref in referenced:
            base = ref.split(".")[0]
            if base in python_keywords:
                continue
            if base not in known_labels:
                findings.append(
                    Finding(
                        check_id="RO-002",
                        severity="error",
                        question_label=term.label,
                        message=f"Term condition references '{base}' which is not a known question label",
                        detail=f"cond: {cond!r}",
                    )
                )
    return findings


def _ro003_goto_targets(xml: SurveyModel) -> list[Finding]:
    """RO-003: <goto> target label exists in the survey."""
    findings = []
    known_labels = xml.labels()
    for goto in [e for e in xml.elements if hasattr(e, "target")]:
        target = goto.target  # type: ignore[attr-defined]
        if target and target not in known_labels:
            findings.append(
                Finding(
                    check_id="RO-003",
                    severity="error",
                    question_label=getattr(goto, "label", "goto"),
                    message=f"<goto> target '{target}' does not exist in the survey",
                )
            )
    return findings


def _ro004_suspend_after_questions(xml: SurveyModel) -> list[Finding]:
    """RO-004: <suspend> present after each respondent-facing question."""
    findings = []
    elements = xml.elements
    for i, el in enumerate(elements):
        if not isinstance(el, XmlQuestion):
            continue
        next_el = elements[i + 1] if i + 1 < len(elements) else None
        if next_el is None or not isinstance(next_el, XmlSuspend):
            findings.append(
                Finding(
                    check_id="RO-004",
                    severity="warning",
                    question_label=el.label,
                    message=f"No <suspend> immediately after question '{el.label}'",
                    detail="Each respondent-facing question should be followed by a <suspend> page break.",
                )
            )
    return findings


def _ro005_cond_has_routing_note(xml: SurveyModel, doc: SurveyModel) -> list[Finding]:
    """RO-005: Questions with a display cond have a routing note in the questionnaire."""
    findings = []
    doc_by_label = {q.label: q for q in doc.questions()}
    for xml_q in xml.questions():
        if not xml_q.cond:
            continue
        doc_q = doc_by_label.get(xml_q.label)
        if doc_q is None:
            continue
        # Routing note present if doc-side has cond OR raw display logic captured
        has_note = bool(doc_q.cond) or (
            doc_q.parser_meta is not None and bool(doc_q.parser_meta.raw_display_logic)
        )
        if not has_note:
            findings.append(
                Finding(
                    check_id="RO-005",
                    severity="warning",
                    question_label=xml_q.label,
                    message=f"Question '{xml_q.label}' has display condition in XML but no routing note in questionnaire",
                    detail=f"cond: {xml_q.cond!r}",
                )
            )
    return findings
