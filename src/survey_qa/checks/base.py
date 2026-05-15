"""Abstract base class for all QA checks."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.models import Finding, ParsedQuestion, XmlQuestion


class Check(ABC):
    """Base class for all QA checks.

    Each subclass implements run() and is automatically registered
    via the @register_check decorator in checks/__init__.py.
    """

    id: str  # e.g. "Q-001" — must be set on each subclass
    description: str  # human-readable name for reports

    @abstractmethod
    def run(self, xml_q: XmlQuestion, q_q: ParsedQuestion) -> list[Finding]:
        """Compare one XML question against its questionnaire counterpart.

        Args:
            xml_q: The parsed XML question (from SurveyModel).
            q_q:   The parsed questionnaire question (source of truth).

        Returns:
            A (possibly empty) list of Finding objects.
        """
        ...

    def _finding(
        self,
        severity: str,
        question_label: str,
        message: str,
        detail: str = "",
    ) -> Finding:
        return Finding(
            check_id=self.id,
            severity=severity,  # type: ignore[arg-type]
            question_label=question_label,
            message=message,
            detail=detail,
        )

    def error(self, label: str, message: str, detail: str = "") -> Finding:
        return self._finding("error", label, message, detail)

    def warning(self, label: str, message: str, detail: str = "") -> Finding:
        return self._finding("warning", label, message, detail)
