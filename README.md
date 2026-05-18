# Survey QA

A Python tool that compares a **Forsta Decipher XML survey script** against a **client questionnaire document** (Word or PDF) and produces a structured QA report. The questionnaire is always the source of truth.

> **Design docs:** the canonical project plan, architecture, and conventions live in [`docs/`](docs/):
> - [`03_BUILD_PLAN.md`](docs/03_BUILD_PLAN.md) — current state, in-flight work, backlog
> - [`04_DECIPHER_XML_REFERENCE.md`](docs/04_DECIPHER_XML_REFERENCE.md) — XML element reference
> - [`05_CODING_CONVENTIONS.md`](docs/05_CODING_CONVENTIONS.md) — how to add checks, models, and question types
> - [`06_RADIO_ELEMENT_REFERENCE.md`](docs/06_RADIO_ELEMENT_REFERENCE.md) — full radio element attributes
> - [`08_COMPACT_FORMAT.md`](docs/08_COMPACT_FORMAT.md) — compact format spec used by the MCP `check_survey` tool
> - [`STALE_01_PROJECT_OVERVIEW.md`](docs/STALE_01_PROJECT_OVERVIEW.md), [`STALE_02_ARCHITECTURE.md`](docs/STALE_02_ARCHITECTURE.md) — pending refresh
>
## What it does

1. Parses the Decipher XML into typed models — questions, rows, routing, structural elements.
2. Lets Claude author a compact-format representation of the questionnaire (after `extract_doc_text` returns text with inline `<b>/<i>/<u>` tags). The deterministic Python parser turns that compact text into the same unified model.
3. Aligns labels between the two sides — exact / case-insensitive / prefix-strip / suffix / fuzzy on labels, plus title similarity when the doc didn't carry labels.
4. Runs all QA checks across question types and routing logic.
5. Reports findings as JSON or a color-coded Excel report.

## How to use it

Distribution is via a single MCP server (MCPB bundle) for Claude Desktop, plus a CLI for batch use.

| Surface | How |
|---|---|
| **Claude Desktop** | Drag `dist/survey-qa.mcpb` in. `uv` (bundled with Desktop) handles Python + deps automatically. Cross-platform. |
| **CLI** | `pip install -e .` then `survey-qa <xml> <questionnaire>` for batch runs or CI. |
| **FastAPI** | `uvicorn survey_qa.api.main:app` for programmatic integration. |

If your org's Extension policy blocks the standard install, use **Settings → Extensions → Advanced Settings → Install Unpacked Extension** and point at `dist/build/` (the unpacked staging directory built by `scripts/build_mcpb.sh`).

---

## Install for Claude Desktop (MCPB)

### Build the `.mcpb` (maintainer)

```bash
scripts/build_mcpb.sh
# Output: dist/survey-qa.mcpb
```

### Install (each team member)

1. Send them `dist/survey-qa.mcpb` (Slack, shared drive, GitHub release).
2. They open Claude Desktop → **Settings → Extensions → Install Extension** → select the file.
3. If org policy blocks it, fall back to **Install Unpacked Extension** pointing at the build directory.

Six tools become available:

- `get_workflow_guide` — returns the compact-format authoring guide
- `parse_xml` — XML → SurveyModel JSON
- `extract_doc_text` — .docx/.pdf → text with inline formatting tags
- `check_survey` — compact-format string + XML path → findings
- `list_checks` — registered checks (debugging)
- `generate_report` — Excel report writer

### Usage

In any conversation, attach the survey XML and the questionnaire (.docx/.pdf) and say:

> "Use survey-qa to QA this survey."

Claude reads the questionnaire, authors a compact-format representation, calls `check_survey`, and explains the findings — optionally writing an Excel report via `generate_report`.

---

## Quick start (CLI / dev)

**Requirements:** Python 3.11+.

```bash
git clone <repo>
cd xml_parser
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api]"

# XML-only scan
survey-qa survey.xml

# Full comparison against a Word questionnaire
survey-qa survey.xml questionnaire.docx

# Write an Excel report
survey-qa survey.xml questionnaire.docx --output report.xlsx
```

The CLI uses the older LLM-based doc parser path (`instructor` + `litellm` + `diskcache`). Configure with `LITELLM_MODEL` and the matching API key in `.env`. Parsed questionnaire results are cached so repeat runs cost nothing.

---

## QA checks

| Group | Checks |
|---|---|
| Universal | Q-001 missing question, Q-002 title match, Q-003 type match, Q-005 optional flag |
| Radio | RA-001–006: row count, row text, exclusive row, open row, `values="order"`, duplicate values |
| Checkbox | CB-001–006: row count, row text, `atleast`, exclusive row, open row, exclusive-last |
| Text | TX-001–003: optional flag, grid row count, grid column count |
| Select | SE-001–002: choice count, choice text |
| Routing | RO-001–005: term labels, term condition labels, goto targets, suspend placement, conditional routing notes |

---

## Project layout

```
src/survey_qa/
├── core/           models + utilities      (no I/O — imported by everything)
├── xml_parser/     lxml XML → SurveyModel  (imports core only)
├── doc_parser/
│   ├── compact_parser.py     Claude-authored compact text → SurveyModel (used by MCP)
│   ├── normalizer.py         label alignment (5 strategies + title similarity)
│   ├── extractor.py          formatting-aware .docx/.pdf → text
│   ├── chunker.py            heuristic block splitting (used by LLM path)
│   ├── docx_parser.py        .docx implementation     ┐
│   ├── pdf_parser.py         .pdf implementation      │ used by the CLI's
│   ├── llm_extractor.py      LLM-driven JSON authoring│ older LLM-JSON path
│   ├── extractor.py / config / base                   ┘
├── checks/         QA check registry       (imports core only)
├── reporters/      Excel report writer     (imports core only)
├── mcp/            FastMCP server (MCPB distribution)
└── api/
    ├── cli.py      typer CLI
    ├── main.py     FastAPI app
    └── routes/qa.py  POST /qa/xml, POST /qa/compare
```

Dependency direction: `core → xml_parser | doc_parser | checks → mcp | api`. Each sub-module can be extracted without circular dependency issues.

---

## API

```bash
uvicorn survey_qa.api.main:app --reload
```

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness check |
| `/qa/xml` | POST | Parse an XML file, return survey summary |
| `/qa/compare` | POST | Parse XML + questionnaire, return findings |

Interactive docs at `http://localhost:8000/docs`.

---

## Development

```bash
pip install -e ".[dev]"
pytest                    # full test suite
pytest --cov=survey_qa    # with coverage
```

### Adding a new check

1. Create a function or class in the relevant `checks/` file.
2. Decorate with `@register_check` (or register in `run_routing_checks` for survey-level checks).
3. Add a test in `tests/test_checks.py`.

No other changes needed — the registry picks it up automatically.

---

## Environment variables (CLI / FastAPI only — the MCP doesn't need any)

| Variable | Default | Description |
|---|---|---|
| `LITELLM_MODEL` | `gpt-4o-mini` | LLM model identifier |
| `GEMINI_API_KEY` | — | Google AI Studio key (if using Gemini) |
| `OPENAI_API_KEY` | — | OpenAI key (if using OpenAI) |
| `ANTHROPIC_API_KEY` | — | Anthropic key (if using Claude) |
| `QA_CACHE_DIR` | `~/.cache/survey_qa` | Disk cache location |
| `QA_LLM_RETRIES` | `3` | Instructor retries on validation failure |
