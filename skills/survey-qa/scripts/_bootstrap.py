"""Shared bootstrap — put the bundled survey_qa package on sys.path.

The Skill bundles the full `survey_qa/` package alongside scripts/. We need
to make sure Python finds it regardless of where the sandbox launches the
script from.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))
