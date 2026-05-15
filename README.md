# Survey QA

A Python tool that compares a **Forsta Decipher XML survey script** against a **client questionnaire document** (Word or PDF) and produces a structured QA report. The questionnaire is always the source of truth.

> **Design docs:** the canonical project plan, architecture, and conventions live in [`docs/`](docs/):
> - [`03_BUILD_PLAN.md`](docs/03_BUILD_PLAN.md) — current state, in-flight work, backlog
> - [`04_DECIPHER_XML_REFERENCE.md`](docs/04_DECIPHER_XML_REFERENCE.md) — XML element reference
> - [`05_CODING_CONVENTIONS.md`](docs/05_CODING_CONVENTIONS.md) — how to add checks, models, and question types
> - [`06_RADIO_ELEMENT_REFERENCE.md`](docs/06_RADIO_ELEMENT_REFERENCE.md) — full radio element attributes
> - [`08_COMPACT_FORMAT.md`](docs/08_COMPACT_FORMAT.md) — doc-side compact format spec (in-progress redesign of the doc parser; under review)
> - `07_DECIPHER_FUNCTION_LIBRARY.md` — Decipher function library (`ans`, `flt`, `label`, etc.); to be added
> - [`STALE_01_PROJECT_OVERVIEW.md`](docs/STALE_01_PROJECT_OVERVIEW.md), [`STALE_02_ARCHITECTURE.md`](docs/STALE_02_ARCHITECTURE.md) — pending refresh; mostly accurate but don't yet reflect the Skill surface or the compact-format redesign
>
## What it does

1. Parses the Decipher XML into typed models — questions, rows, routing, structural elements.
2. Parses the questionnaire document using a two-stage pipeline: local text extraction followed by an LLM call that returns structured data. Results are cached so repeat runs cost nothing.
3. Aligns labels between the two sources using a five-pass fuzzy matching strategy (exact → case-insensitive → prefix strip → suffix → fuzzy).
4. Runs 26 QA checks across question types and routing logic.
5. Reports findings as a rich CLI table and/or an Excel report.

## Four ways to use it

| Mode | Best for | Needs API key |
|---|---|---|
| **Skill (claude.ai / Desktop / Code)** | Primary team-distribution path — works across all Claude surfaces, no per-user setup | No (Claude does the doc parsing in its sandbox) |
| **MCPB (Claude Desktop)** | Drag-and-drop install for Claude Desktop users specifically | Yes (server-side, for the instructor doc parser) |
| **CLI** | Batch runs, CI/CD, scripting | Yes (OpenAI / Anthropic / Gemini / Ollama) |
| **FastAPI** | Programmatic integration | Yes |

The Skill bundles the same Python library as the other surfaces, but the doc parsing happens in Claude's reasoning + a deterministic compact-text parser (in progress — see [`docs/08_COMPACT_FORMAT.md`](docs/08_COMPACT_FORMAT.md)) instead of via instructor + litellm. That's why the Skill doesn't need an API key.

See [Install for Claude Desktop](#install-for-claude-desktop-mcpb) below for the MCPB path. See `dist/survey-qa-skill.zip` (built via `scripts/build_skill.sh`) for the Skill bundle to upload.

---

## Quick start

**Requirements:** Python 3.12+, an LLM API key.

```bash
# Clone and set up
git clone <repo>
cd xml_parser
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api]"

# Configure (copy and edit)
cp .env.example .env

# XML-only scan (no LLM, free)
survey-qa survey.xml

# Full comparison against a Word questionnaire
survey-qa survey.xml questionnaire.docx

# Write an Excel report
survey-qa survey.xml questionnaire.docx --output report.xlsx
```

---

## LLM provider

The tool uses [`litellm`](https://docs.litellm.ai) as a provider abstraction — switching models is a single env-var change, no code changes required.

Set `LITELLM_MODEL` and the matching API key in `.env`:

```bash
# OpenAI (default)
LITELLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Google Gemini via AI Studio
LITELLM_MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=...

# Anthropic
LITELLM_MODEL=claude-3-haiku-20240307
ANTHROPIC_API_KEY=sk-ant-...

# Local (no key needed)
LITELLM_MODEL=ollama/llama3
```

Parsed questionnaire results are cached on disk. Re-running on the same file costs $0.

---

## Install for Claude Desktop (MCPB)

The simplest way to use this tool — and the path for sharing with your team — is to install it as a Claude Desktop Extension. No terminal, no API key required (Claude does the doc parsing natively from the conversation).

### Build the `.mcpb` file (maintainer)

```bash
scripts/build_mcpb.sh
# Output: dist/survey-qa.mcpb (~44 KB)
```

### Install (each team member)

1. Send them the `dist/survey-qa.mcpb` file (Slack, shared drive, GitHub release).
2. They open Claude Desktop, drag the `.mcpb` onto the window, click "Install."
3. Done. Five tools become available in their Claude Desktop:
   - `parse_xml`, `run_checks`, `list_checks`, `generate_report`, `get_survey_model_schema`

### Usage in Claude Desktop

In any conversation, attach the questionnaire (.docx/.pdf) and the survey XML, then ask:

> "Use survey-qa to compare survey.xml against this questionnaire and tell me what's broken."

Claude reads the questionnaire, calls `parse_xml`, builds a doc-side `SurveyModel`, calls `run_checks`, and explains the findings — optionally writing an Excel report via `generate_report`.

### Manual registration (alternative to MCPB)

If you'd rather skip the MCPB packaging and register the MCP server directly from source, add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "survey-qa": {
      "command": "/absolute/path/to/.venv/bin/survey-qa-mcp"
    }
  }
}
```

Restart Claude Desktop. Same five tools become available.

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
├── doc_parser/     docx/pdf + LLM → QuestionnaireModel
│   ├── base.py             abstract parser + file-extension factory
│   ├── config.py           LLMConfig loaded from env
│   ├── extractor.py        stage 1: raw text extraction
│   ├── chunker.py          stage 1: heuristic block splitting
│   ├── docx_parser.py      .docx implementation
│   ├── pdf_parser.py       .pdf implementation
│   ├── llm_extractor.py    stage 2: instructor + litellm + diskcache
│   └── normalizer.py       fuzzy label alignment
├── checks/         QA check registry       (imports core only)
├── reporters/      Excel report writer     (imports core only)
└── api/
    ├── cli.py      typer CLI
    ├── main.py     FastAPI app
    └── routes/qa.py  POST /qa/xml, POST /qa/compare
```

Dependency direction is strictly one-way: `core → xml_parser | doc_parser | checks → api`. Each sub-module can be extracted into its own package without circular dependency issues.

---

## API

Start the server:

```bash
uvicorn survey_qa.api.main:app --reload
```

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness check |
| `/qa/xml` | POST | Parse an XML file, return survey summary |
| `/qa/compare` | POST | Parse XML + questionnaire, return findings |

Interactive docs available at `http://localhost:8000/docs`.

---

## Development

```bash
pip install -e ".[dev]"
pytest                    # 124 tests
pytest --cov=survey_qa    # with coverage
```

### Adding a new check

1. Create a function or class in the relevant `checks/` file.
2. Decorate with `@register_check` (or call `run_routing_checks` for survey-level checks).
3. Add a test in `tests/test_checks.py`.

No other changes needed — the registry picks it up automatically.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `LITELLM_MODEL` | `gpt-4o-mini` | LLM model identifier |
| `GEMINI_API_KEY` | — | Google AI Studio key (if using Gemini) |
| `OPENAI_API_KEY` | — | OpenAI key (if using OpenAI) |
| `ANTHROPIC_API_KEY` | — | Anthropic key (if using Claude) |
| `QA_CACHE_DIR` | `~/.cache/survey_qa` | Disk cache location |
| `QA_LLM_RETRIES` | `3` | Instructor retries on validation failure |
