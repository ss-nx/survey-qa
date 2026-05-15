# Survey QA Tool — Project Overview

## What This Is

A Python-based QA automation tool that compares a client questionnaire document (Word/PDF) against a Forsta Decipher XML survey script and outputs a structured report identifying discrepancies.

The questionnaire is always the **source of truth**. The XML is what gets validated against it.

The tool ships in two modes:

- **CLI / FastAPI** — for automated, batch, or CI/CD runs
- **MCP server** — for interactive use inside Claude, where findings can be explained, reasoned about, and acted on in conversation

---

## Problem Being Solved

Survey programmers manually check that XML scripts match client questionnaires before launch. This is slow and error-prone. Common mistakes include:

- Missing or extra answer options
- Wrong option values (`value="1"` vs `value="2"`)
- Misspelled question or option text
- Wrong question type (radio vs checkbox)
- Incorrect or missing display conditions (`cond=`)
- Routing/skip logic errors
- Missing questions entirely

---

## Key Constraints

- **Questionnaire format varies by client** — no guaranteed column structure. Could be Word, PDF, or other formats. The doc parser must be flexible.
- **XML is always Forsta Decipher format** — well-structured, deterministic, parseable.
- **LLM cost must be controlled** — doc parsing calls an LLM; results are cached by content hash so re-runs against the same document are free.
- **Non-technical users** need to be able to run this eventually — interactive MCP mode addresses this without requiring a terminal.
- **Extensibility is a priority** — new checks and new question types should be easy to add without touching core logic.
- **Check changes go through review** — any addition, modification, or removal of a check triggers a GitHub branch + PR so changes are reviewed before going live.

---

## Users

- **Primary**: Survey programmers / QA staff who write and review Decipher XML daily
- **Interactive**: Any team member running QA through a Claude conversation (MCP mode)
- **Future**: Project managers or coordinators running QA via a simple UI

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.12+ | Team familiarity, rich XML/doc libraries |
| XML parsing | `lxml` | Deterministic, no AI needed for well-structured XML |
| Doc text extraction | `python-docx`, `pdfplumber` | Zero-cost local extraction before LLM step |
| LLM extraction | `instructor` + `litellm` | Schema-enforced output with retries; provider-agnostic (OpenAI, Anthropic, Ollama) |
| LLM caching | `diskcache` (SHA-256 keyed) | Re-running against the same document costs nothing |
| Data models | `Pydantic v2` | Validation, discriminated unions, serialization |
| Fuzzy matching | `rapidfuzz` | Handles label/text variations robustly |
| CLI | `typer` | Clean argument parsing, exit codes |
| REST API | `FastAPI` | Enables programmatic and future UI integration |
| Reporting | `openpyxl` + `rich` | Color-coded Excel report + terminal output |
| MCP server | `mcp` SDK | Interactive mode inside Claude |
| Check management | GitHub MCP | Branch + PR workflow for check changes |
| UI (future) | Streamlit | Drag-and-drop files, download report |
