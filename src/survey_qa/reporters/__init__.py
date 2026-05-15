"""Reporters — convert findings into output formats.

Dependency direction: core only.
"""

from .excel import write_report

__all__ = ["write_report"]
