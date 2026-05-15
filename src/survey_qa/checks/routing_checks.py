"""Routing QA checks (RO-001 through RO-005).

Routing checks operate differently from question-level checks:
they receive the full SurveyModel and QuestionnaireModel, not a single question pair.
They are invoked separately via run_routing_checks().
"""

from __future__ import annotations

import re

from ..core.models import Finding, QuestionnaireModel, SurveyModel, XmlQuestion, XmlSuspend


_LABEL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")


def run_routing_checks(survey: SurveyModel, questionnaire: QuestionnaireModel) -> list[Finding]:
    """Run all routing checks and return findings."""
    findings: list[Finding] = []
    findings.extend(_ro001_term_labels(survey, questionnaire))
    findings.extend(_ro002_term_cond_labels(survey))
    findings.extend(_ro003_goto_targets(survey))
    findings.extend(_ro004_suspend_after_questions(survey))
    findings.extend(_ro005_cond_has_routing_note(survey, questionnaire))
    return findings


def _ro001_term_labels(survey: SurveyModel, questionnaire: QuestionnaireModel) -> list[Finding]:
    """RO-001: Every <term> label matches an expected terminate in the questionnaire."""
    findings = []
    q_routing_labels: set[str] = set()
    for q in questionnaire.questions:
        for rule in q.routing_rules:
            # extract anything that looks like a term label from routing text
            q_routing_labels.update(_LABEL_RE.findall(rule))

    for term in survey.terms():
        if q_routing_labels and term.label not in q_routing_labels:
            findings.append(
                Finding(
                    check_id="RO-001",
                    severity="warning",
                    question_label=term.label,
                    message=f"Term '{term.label}' (cond: {term.cond!r}) not referenced in questionnaire routing rules",
                )
            )
    return findings


def _ro002_term_cond_labels(survey: SurveyModel) -> list[Finding]:
    """RO-002: <term> condition references question labels that exist in the survey."""
    findings = []
    known_labels = survey.labels()

    for term in survey.terms():
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


def _ro003_goto_targets(survey: SurveyModel) -> list[Finding]:
    """RO-003: <goto> target label exists in the survey."""
    findings = []
    known_labels = survey.labels()
    for goto in [e for e in survey.elements if hasattr(e, "target")]:
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


def _ro004_suspend_after_questions(survey: SurveyModel) -> list[Finding]:
    """RO-004: <suspend> present after each respondent-facing question."""
    findings = []
    elements = survey.elements
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


def _ro005_cond_has_routing_note(
    survey: SurveyModel, questionnaire: QuestionnaireModel
) -> list[Finding]:
    """RO-005: Questions with a display cond have a routing note in the questionnaire."""
    findings = []
    for xml_q in survey.questions():
        if not xml_q.cond:
            continue
        q_q = questionnaire.by_label(xml_q.label)
        if q_q is None:
            continue
        if not q_q.routing_rules:
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
