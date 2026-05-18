"""Shared bootstrap — runtime Python + dependency setup for Skill scripts.

The Skill bundle ships the `survey_qa/` Python source but NOT a Python
interpreter or third-party deps (lxml, pydantic, etc.). When the Skill is
unpacked into Claude Desktop or Claude Code, scripts may launch under:

  - The wrong Python version (macOS's Xcode Python is 3.9; we use PEP 604
    union syntax which is 3.10+; pydantic v2 evaluates hints at runtime).
  - A Python that's missing our third-party deps.

This bootstrap handles both:

  1. If the launched Python is < 3.11, search PATH for python3.13/3.12/3.11
     and `os.execv` into it. Fail loudly if none found.
  2. If any required third-party dep is missing, pip-install into a
     Python-version-specific `vendor/pyX.Y/` directory using the runtime
     Python so wheels match the runtime ABI.

After both gates pass, the scripts can `from survey_qa... import ...`
normally.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── 1. Python version gate ────────────────────────────────────────────────

_MIN_PY = (3, 11)

if sys.version_info < _MIN_PY:
    for _candidate in ("python3.13", "python3.12", "python3.11"):
        _path = shutil.which(_candidate)
        if _path:
            print(
                f"[survey-qa skill] Re-launching under {_candidate} "
                f"(survey-qa needs Python {_MIN_PY[0]}.{_MIN_PY[1]}+; "
                f"got {sys.version.split()[0]}).",
                file=sys.stderr,
                flush=True,
            )
            os.execv(_path, [_path, *sys.argv])
    raise RuntimeError(
        f"survey-qa requires Python {_MIN_PY[0]}.{_MIN_PY[1]}+ "
        f"(got {sys.version_info.major}.{sys.version_info.minor}). "
        f"None of python3.13/3.12/3.11 were found on PATH. "
        f"Install via `brew install python@3.11` (or 3.12/3.13)."
    )

# ── 2. Make the bundled survey_qa package + previous vendor/ importable ──

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_VENDOR = _SKILL_ROOT / "vendor" / f"py{sys.version_info.major}.{sys.version_info.minor}"

if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

# ── 3. Self-install missing third-party deps on first run ─────────────────

# (import_name, pip_spec) pairs — third-party deps required by Skill scripts.
_REQUIRED = (
    ("lxml", "lxml>=5.3"),
    ("docx", "python-docx>=1.1"),
    ("pdfplumber", "pdfplumber>=0.11"),
    ("pydantic", "pydantic>=2.10"),
    ("openpyxl", "openpyxl>=3.1"),
    ("rapidfuzz", "rapidfuzz>=3.10"),
)


def _missing() -> list[str]:
    missing: list[str] = []
    for import_name, pip_spec in _REQUIRED:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pip_spec)
    return missing


def _install(specs: list[str]) -> None:
    print(
        f"[survey-qa skill] First-run setup: installing dependencies into "
        f"{_VENDOR} (one-time, ~30s)...",
        file=sys.stderr,
        flush=True,
    )
    _VENDOR.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(_VENDOR),
            "--quiet",
            "--disable-pip-version-check",
            *specs,
        ]
    )
    if str(_VENDOR) not in sys.path:
        sys.path.insert(0, str(_VENDOR))
    importlib.invalidate_caches()


_to_install = _missing()
if _to_install:
    _install(_to_install)
