"""Finding model — output of the check layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Finding(BaseModel):
    """A single QA discrepancy raised by a check."""

    check_id: str
    severity: Literal["error", "warning", "info"]
    question_label: str
    message: str
    detail: str = ""
