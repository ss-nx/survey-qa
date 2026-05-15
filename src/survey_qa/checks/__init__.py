"""Check registry and runner.

Usage:
    from survey_qa.checks import register_check, run_checks

    @register_check
    class MyCheck(Check):
        id = "XX-001"
        ...

    findings = run_checks(survey_model, questionnaire_model)
"""

from __future__ import annotations

from ..core.models import Finding, QuestionnaireModel, SurveyModel, XmlQuestion
from .base import Check

_registry: list[type[Check]] = []


def register_check(cls: type[Check]) -> type[Check]:
    """Decorator that registers a Check subclass into the global registry."""
    _registry.append(cls)
    return cls


def registered_checks() -> list[type[Check]]:
    """Return all registered check classes (ordered by registration)."""
    return list(_registry)


def run_checks(survey: SurveyModel, questionnaire: QuestionnaireModel) -> list[Finding]:
    """Run all registered checks against every XML question that has a questionnaire match.

    Questions in the XML that have no counterpart in the questionnaire are NOT
    skipped silently — Q-001 will raise an error for them.
    """
    # Import side-effect: registers all checks
    from . import (  # noqa: F401
        checkbox_checks,
        question_checks,
        radio_checks,
        routing_checks,
        select_checks,
        text_checks,
    )

    findings: list[Finding] = []
    check_instances = [cls() for cls in _registry]

    xml_questions: list[XmlQuestion] = survey.questions()

    for xml_q in xml_questions:
        q_q = questionnaire.by_label(xml_q.label)

        if q_q is None:
            findings.append(
                Finding(
                    check_id="Q-001",
                    severity="error",
                    question_label=xml_q.label,
                    message=f"Question '{xml_q.label}' not found in questionnaire",
                )
            )
            continue

        for check in check_instances:
            try:
                findings.extend(check.run(xml_q, q_q))
            except Exception as exc:
                findings.append(
                    Finding(
                        check_id=check.id,
                        severity="error",
                        question_label=xml_q.label,
                        message=f"Check {check.id} raised an unexpected error",
                        detail=str(exc),
                    )
                )

    return findings
