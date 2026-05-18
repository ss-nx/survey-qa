# Survey QA Tool — Build Plan

## Guiding Principles

- **Start simple, add complexity gradually.**
- **Each phase is independently shippable** — every phase produces something runnable.
- **Checks are the product** — the architecture exists to make adding checks easy.
- **Control LLM cost from day one** — caching, schema discipline, no asking the LLM to do what code can do.
- **Check changes go through review** — no check reaches production without a GitHub PR.

---

## What's done

### Phase 1 — XML Parser + Core Checks ✅

Deterministic lxml-based parser produces `SurveyModel` containing `XmlElement` instances. Q-checks (title, type, optional) and RA-checks (radio row count/text/exclusive/open/values/duplicates). Console reporter, `typer` CLI.

### Phase 2 — Doc Parser + Caching ✅

Three-stage doc parser: text extraction (`python-docx`/`pdfplumber`) → regex chunking → LLM extraction via `instructor` + `litellm`. Disk cache keyed by `SHA-256(text + model + schema_version)`. Excel reporter. FastAPI endpoints.

### Phase 3 — Full check coverage ✅

CB-checks (checkbox), TX-checks (text/grid), SE-checks (select), RO-checks (routing). 26 checks total.

### Unified-model refactor ✅

Both parsers produce the same `XmlElement` types — no separate `QuestionnaireModel`. `ParserMeta` field carries doc-side annotations (`source`, `confidence`, `raw_display_logic`, etc.) that checks ignore and reporters surface. Check signatures take same type on both sides. 124/124 tests pass.

### Phase 5 — MCP Server ✅ (POC)

`survey_qa.mcp.server` exposes five tools (`get_survey_model_schema`, `parse_xml`, `run_checks`, `list_checks`, `generate_report`). `survey-qa-mcp` console script. Local stdio transport. Validated against the fixture XML; not yet validated against a real questionnaire end-to-end.

### MCPB packaging ✅

`manifest.json` + `scripts/build_mcpb.sh` produce `dist/survey-qa.mcpb` for Claude Desktop install. `uv` (bundled with Desktop) handles Python + deps automatically, so distribution is cross-platform with zero per-user setup. This is the sole supported team-distribution path.

### Compact-format authoring ✅

The MCP `check_survey` tool accepts a compact text format Claude authors from the questionnaire (instead of the older approach where Claude had to author the entire doc-side `SurveyModel` as JSON inline — ~100 KB of structured output, prone to malformed JSON, slow). The deterministic `compact_parser.py` turns it into the same unified model.

**Spec:** [`08_COMPACT_FORMAT.md`](08_COMPACT_FORMAT.md). Inline guide returned by the `get_workflow_guide` MCP tool.

### Skill packaging — retired

Earlier work shipped a Skill bundle (`skills/survey-qa/` + `scripts/build_skill.sh`). It was retired after the Cowork sandbox revealed the Skill design fundamentally couldn't survive read-only filesystems and locked Python versions. The MCP path works in those environments because `uv`/Anthropic provides the runtime. All Skill files were removed.

---

## Backlog (not yet started)

### Phase 4 — Display condition comparison

Compare `cond` expressions between XML and doc. Once the compact format is locked and the Decipher function library reference (`07_DECIPHER_FUNCTION_LIBRARY.md`) is in place, both parsers can populate `cond` with Decipher syntax. Comparison becomes an AST diff.

**Deliverables:**
- `survey_qa/checks/condition_checks.py`
- `survey_qa/checks/condition_ast.py` — Decipher expression parser → AST

**Checks:**

| Check | Severity |
|---|---|
| XML has `cond=` but doc-side `cond` is `None` | WARNING |
| Doc has logic note in `parser_meta.raw_display_logic` but XML has no `cond=` | ERROR |
| Both have `cond=` but AST diff shows mismatch | ERROR |
| Doc-side `cond` references a label not present in the XML | INFO |

### Phase 6 — GitHub PR workflow for check management

Team members describe check changes in a Claude conversation. Claude (using the official GitHub MCP server) creates a branch, commits the generated check class, and opens a PR for owner review. No new code in this project — it's a usage pattern + a PR template + owner-side review discipline.

**Deliverables:**
- `.github/PULL_REQUEST_TEMPLATE/check_change.md`
- Branch-naming convention documented (`checks/add-{id}`, `checks/modify-{id}`, `checks/remove-{id}`)

### Phase 7 — Streamlit UI

Backlog. Skill (Phase 5) and MCPB cover the no-terminal use case for users with Claude access. Streamlit is only valuable for users without Claude access who want a browser experience.

### Decipher function library reference

`docs/07_DECIPHER_FUNCTION_LIBRARY.md` — to be provided. Documents `ans`, `flt`, `label`, etc. so the doc parser can translate plain-English display logic into Decipher syntax (Phase 4).

---

## Surfaces and their statuses

| Surface | Status | Doc parser path | Needs API key |
|---|---|---|---|
| CLI (`survey-qa`) | ✅ Done | instructor + litellm | Yes |
| FastAPI | ✅ Done | instructor + litellm | Yes |
| MCP server (local) | ✅ POC | instructor + litellm | Yes (server-side) |
| MCPB (Claude Desktop) | ✅ Built | same as MCP | Yes |
| **Skill** (claude.ai / Desktop / Code) | ✅ v1 in test | **Claude in conversation** | **No** |

The Skill is the primary path now that the team has settled on no-API-key constraints. The other surfaces remain useful for batch/CI use cases that have keys.

---

## Package Structure

```
src/survey_qa/
├── core/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── xml.py             # XmlElement union + ParserMeta + per-type models
│   │   └── finding.py
│   └── utils.py
├── xml_parser/
│   └── __init__.py            # lxml parser → SurveyModel (deterministic, no LLM)
├── doc_parser/
│   ├── extractor.py           # docx/pdf → plain text
│   ├── chunker.py             # text → question-candidate batches
│   ├── llm_extractor.py       # instructor + litellm + diskcache → SurveyModel
│   ├── normalizer.py          # label alignment (will gain title-similarity)
│   ├── compact_parser.py      # PENDING — compact text → SurveyModel (v2 doc path)
│   ├── base.py
│   ├── docx_parser.py
│   └── pdf_parser.py
├── checks/
│   ├── __init__.py            # @register_check decorator + run_checks()
│   ├── base.py
│   ├── question_checks.py     # Q-checks
│   ├── radio_checks.py        # RA-checks
│   ├── checkbox_checks.py     # CB-checks
│   ├── text_checks.py         # TX-checks
│   ├── select_checks.py       # SE-checks
│   ├── routing_checks.py      # RO-checks
│   └── condition_checks.py    # PENDING — Phase 4
├── reporters/
│   └── excel.py
├── api/
│   ├── cli.py
│   ├── main.py
│   └── routes/qa.py
└── mcp/
    ├── server.py              # FastMCP entry point
    └── __init__.py

manifest.json                  # MCPB manifest

scripts/
└── build_mcpb.sh
```
