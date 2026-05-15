# Survey QA Tool — Build Plan

## Guiding Principles

- **Start simple, add complexity gradually** — Phase 1 should produce real, useful output against a real survey
- **Don't over-engineer early** — get the pipeline working end-to-end before adding every check type
- **Each phase is independently shippable** — every phase produces something runnable
- **Checks are the product** — the architecture exists to make adding checks easy
- **Control LLM cost from day one** — caching is not an optimisation, it's a requirement
- **Check changes go through review** — no check reaches production without a GitHub PR

---

## Phase 1 — XML Parser + Core Checks ✅ DONE

**Goal**: Parse the Decipher XML into the canonical model and run a first set of checks.

**Deliverables**:
- `survey_qa/core/models/` — Pydantic model package: `xml.py` (`XmlElement` discriminated union with `_meta` field), `finding.py` (`Finding`, `Severity`), `__init__.py` re-exports
- `survey_qa/xml_parser/__init__.py` — `lxml`-based parser → `SurveyModel`
- `survey_qa/checks/__init__.py` — `@register_check` decorator + `run_checks()` runner
- `survey_qa/checks/base.py` — abstract `Check` base class
- `survey_qa/checks/question_checks.py` — Q-checks (title match, type match, optional match)
- `survey_qa/checks/radio_checks.py` — RA-checks (row count, row text, exclusive, open, values, duplicates)
- `survey_qa/api/cli.py` — `typer` CLI entry point with `rich` terminal output

**Checks in Phase 1**:

| Check ID | Description | Severity |
|---|---|---|
| Q-001 | Question in doc missing from XML | ERROR |
| Q-002 | Question title mismatch (fuzzy ≥ 90%) | WARNING |
| Q-003 | Question type mismatch | ERROR |
| Q-005 | Required/optional mismatch | WARNING |
| RA-001 | Row count mismatch | ERROR |
| RA-002 | Row text mismatch | WARNING |
| RA-003 | Missing exclusive option | WARNING |
| RA-004 | Missing open-end option | ERROR |
| RA-005 | Option value mismatch | ERROR |
| RA-006 | Duplicate option values | ERROR |

**Key decisions**:
- Use **Pydantic v2** (not plain dataclasses) — validation, discriminated unions, serialization
- Use **`@register_check` decorator** (not a manual dict) — zero wiring for new checks
- Strip HTML from `<title>` before comparison

---

## Phase 2 — Doc Parser + Caching ✅ DONE

**Goal**: Parse real Word/PDF questionnaires using LLM extraction. Control cost with caching.

**Deliverables**:
- `survey_qa/doc_parser/extractor.py` — `python-docx` + `pdfplumber` → plain text
- `survey_qa/doc_parser/chunker.py` — regex-based chunking (~6k chars/batch)
- `survey_qa/doc_parser/llm_extractor.py` — `instructor` + `litellm` → `SurveyModel` (the unified model), `diskcache` by `SHA-256(text + model + schema_version)`
- `survey_qa/doc_parser/normalizer.py` — label alignment (exact → case → prefix → suffix → fuzzy)
- `survey_qa/reporters/excel.py` — `openpyxl` Excel report (Summary, Findings, Questions sheets)
- `survey_qa/api/main.py` + `routes/qa.py` — FastAPI: `POST /qa/xml`, `POST /qa/compare`

**Key decisions**:
- **Doc parser produces the unified `SurveyModel`** — same Pydantic types as the XML parser (`XmlRadio`, `XmlCheckbox`, etc.). No separate `QuestionnaireModel` / `ParsedQuestion`.
- Doc parser fills in fields it can extract; leaves unsupported fields as `None`.
- Populates the optional `_meta: ParserMeta` field with confidence, source excerpt, and ambiguity notes.
- Translates plain-English display logic into Decipher syntax for `cond` using the function library reference (see `07_DECIPHER_FUNCTION_LIBRARY.md`). If translation fails, leaves `cond = None` and stores the raw English in `_meta.raw_display_logic`.
- Use **`instructor`** (not raw API calls) — schema-enforced output, automatic retries on malformed response
- Use **`litellm`** (not direct Anthropic SDK) — swap providers via config
- **Cache by content hash + schema version** — same document = zero cost on re-run; model schema changes invalidate the cache automatically
- **Label normalization is mandatory** — call `normalize_labels()` before running checks; skipping it produces false Q-001 positives

**Cost estimates** (with cache misses):

| Questions | Approximate cost |
|---|---|
| 50 | ~$0.003 |
| 100 | ~$0.005 |
| 200 | ~$0.010 |
| Re-run (any size) | $0.000 |

---

## Phase 3 — Checkbox, Text, Select, Routing Checks ✅ DONE

**Goal**: Full check coverage across all question types and routing logic.

**Deliverables**:
- `survey_qa/checks/checkbox_checks.py` — CB-checks (mirrors RA-checks for multi-select)
- `survey_qa/checks/text_checks.py` — TX-checks (optional flag, grid row count)
- `survey_qa/checks/select_checks.py` — SE-checks (choice count, choice text)
- `survey_qa/checks/routing_checks.py` — RO-checks (term labels, conditions, goto targets, suspend placement, routing notes)

**Checks added**:

| Check ID | Description | Severity |
|---|---|---|
| CB-001–006 | Checkbox equivalents of RA-checks | various |
| TX-001 | Text question optional mismatch | WARNING |
| TX-002 | Grid row count mismatch | ERROR |
| SE-001 | Select choice count mismatch | ERROR |
| SE-002 | Select choice text mismatch | WARNING |
| RO-001 | Term label referenced but not found | ERROR |
| RO-002 | Condition references undefined label | ERROR |
| RO-003 | Goto target does not exist | ERROR |
| RO-004 | Suspend placement unexpected | WARNING |
| RO-005 | Routing note in doc not reflected in XML | WARNING |

---

## Phase 4 — Display Condition Comparison

**Goal**: Compare `cond=` expressions in the XML against the doc-side `cond=` (translated from plain English by the doc parser, using the Decipher function library reference).

**Deliverables**:
- `survey_qa/checks/condition_checks.py` — condition comparison checks
- `survey_qa/checks/condition_ast.py` — Decipher expression parser → AST for equivalence comparison

**Key design**:
- Both parsers populate `cond` with Decipher syntax. The doc parser translates plain English using `07_DECIPHER_FUNCTION_LIBRARY.md` as reference.
- Comparison becomes a direct AST diff — no LLM-judged semantic equivalence needed at check time.
- If the doc parser couldn't produce valid syntax, `cond = None` on the doc side and the raw English lives in `_meta.raw_display_logic`. The check fires on that case.

**Checks**:

| Check | Severity |
|---|---|
| XML has `cond=` but doc-side `cond` is `None` (translation failed) | WARNING |
| Doc has logic note in `_meta.raw_display_logic` but XML has no `cond=` | ERROR |
| Both have `cond=` but AST diff shows mismatch | ERROR |
| Doc-side `cond` references a label not present in the XML | INFO |

---

## Phase 5 — MCP Server

**Goal**: Expose the tool as an MCP server so team members can run QA interactively inside Claude, without needing a terminal.

**Deliverables**:
- `survey_qa/mcp/server.py` — MCP server entry point
- `survey_qa/mcp/tools.py` — MCP tool definitions

**MCP tools**:

| Tool | Input | Output |
|---|---|---|
| `parse_xml` | XML file path | Structured `SurveyModel` summary |
| `run_checks` | XML path + questionnaire path | `list[Finding]` |
| `generate_report` | Findings + output path | Excel file path |
| `list_checks` | — | All registered checks with descriptions |

**How interactive mode changes the pipeline**:

In CLI/API mode, the doc parser calls an LLM to extract structure from the questionnaire. In MCP mode, **Claude reads the questionnaire natively** as part of the conversation — the extraction pipeline is bypassed. Only `parse_xml()` and `run_checks()` are needed. This is both simpler and more accurate for unusual questionnaire formats.

**Example interaction**:
```
User: "Check survey.xml against questionnaire.docx"
Claude: [calls parse_xml(survey.xml)]
Claude: [reads questionnaire.docx directly]
Claude: [calls run_checks()]
Claude: "Found 4 issues. 2 errors: Q7 has a type mismatch (doc says radio, XML has checkbox),
         and S3 is missing option r4. 2 warnings: minor text differences on Q2 and Q9.
         Want me to show the suggested XML fixes?"
```

---

## Phase 6 — GitHub Check Management Workflow

**Goal**: Team members can propose check additions, modifications, or removals through a Claude conversation. All changes go through a GitHub PR before going live.

**Deliverables**:
- GitHub MCP configured with write access to the repo
- PR template for check changes (`PULL_REQUEST_TEMPLATE/check_change.md`)
- Branch naming convention: `checks/add-{id}`, `checks/modify-{id}`, `checks/remove-{id}`

**Workflow**:

```
1. Team member: "Add a check that warns if a radio question has more than 15 options"
2. Claude generates the check class following the @register_check pattern
3. GitHub MCP creates branch: checks/add-opt001-max-options
4. GitHub MCP commits the new file to survey_qa/checks/
5. GitHub MCP opens PR, adds owner as reviewer, describes what the check does
6. Owner reviews the generated code
7. Merge → check is live on next server restart
   Reject → change never reaches production
```

**This applies to**:
- Adding a new check
- Modifying a check's logic, threshold, or severity
- Disabling or removing a check

**PR auto-description includes**:
- Check ID and description
- What conditions trigger it
- Severity level
- Who requested it and why
- Example finding output

---

## Phase 7 — Web UI (Streamlit)

**Goal**: Non-technical users can run the tool without a terminal or Claude conversation.

**Deliverables**:
- `app.py` — Streamlit app
- Upload form: questionnaire doc + XML → run → download Excel report
- Summary view: ERROR / WARNING / INFO counts per question
- No login required (internal tool)

**Note**: MCP mode (Phase 5) largely covers the non-technical user need. Streamlit adds value for users who want a standalone browser experience without needing Claude access.

---

## Future / Backlog

- Support for Excel-format questionnaires
- Pipe-in / carry-forward text validation (`${Q1}` references)
- Grid / matrix question type support (cols in canonical model)
- `<comment>` element parsing (sub-title text)
- Side-by-side HTML diff view
- Integration with Decipher API to pull XML directly
- CI/CD hook — run QA check on XML commit
- Per-client check profiles (enable/disable checks per client)
- Natural language check definitions (team describes rules; Claude evaluates at runtime)

---

## Package Structure

```
survey_qa/
├── core/
│   ├── models/
│   │   ├── __init__.py        # re-exports
│   │   ├── xml.py             # XmlElement union + ParserMeta + per-type models
│   │   └── finding.py         # Finding, Severity
│   └── utils.py               # strip_html(), fuzzy match helpers
├── xml_parser/
│   └── __init__.py            # lxml parser → SurveyModel (deterministic, no LLM)
├── doc_parser/
│   ├── extractor.py           # docx/pdf → plain text (zero cost)
│   ├── chunker.py             # text → question-candidate batches
│   ├── llm_extractor.py       # instructor + litellm + diskcache → SurveyModel (unified)
│   └── normalizer.py          # label alignment (fuzzy matching)
├── checks/
│   ├── __init__.py            # @register_check decorator + run_checks()
│   ├── base.py                # abstract Check class
│   ├── question_checks.py     # Q-checks (title, type, optional)
│   ├── radio_checks.py        # RA-checks
│   ├── checkbox_checks.py     # CB-checks
│   ├── text_checks.py         # TX-checks
│   ├── select_checks.py       # SE-checks
│   ├── routing_checks.py      # RO-checks
│   └── condition_checks.py    # Phase 4: display condition checks
├── reporters/
│   └── excel.py               # openpyxl: Summary + Findings + Questions sheets
├── api/
│   ├── cli.py                 # typer CLI (rich console output)
│   ├── main.py                # FastAPI app
│   └── routes/
│       └── qa.py              # POST /qa/xml, POST /qa/compare
└── mcp/                       # Phase 5
    ├── server.py              # MCP server entry point
    └── tools.py               # parse_xml, run_checks, generate_report, list_checks
```
