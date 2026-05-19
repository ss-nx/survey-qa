"""LLM and cache configuration — read from environment variables.

Environment variables:
    LITELLM_MODEL   LLM model identifier understood by litellm (default: gpt-4o-mini)
    QA_CACHE_DIR    Directory for diskcache (default: ~/.cache/survey_qa)
    QA_LLM_RETRIES  Max retries on a failed compact-format parse (default: 3)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LLMConfig:
    model: str
    cache_dir: Path
    max_retries: int


def load_config() -> LLMConfig:
    return LLMConfig(
        model=os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
        cache_dir=Path(os.getenv("QA_CACHE_DIR", "~/.cache/survey_qa")).expanduser(),
        max_retries=int(os.getenv("QA_LLM_RETRIES", "3")),
    )
