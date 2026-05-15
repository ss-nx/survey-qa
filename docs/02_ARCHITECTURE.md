# Survey QA Tool — Architecture & Design Decisions

## High-Level Architecture

```
┌─────────────────────┐        ┌─────────────────────┐
│  Questionnaire doc  │        │   Decipher XML       │
│  (Word / PDF)       │        │   (survey script)    │
│  SOURCE OF TRUTH    │        │                      │
└────────┬────────────┘        └──────────┬───────────┘
         │                                │
         ▼                                ▼
┌─────────────────────┐        ┌─────────────────────┐
│    Doc Parser       │        │    XML Parser        │
│  extractor          │        │  (lxml, deterministic│
│  → chunker          │        │   no LLM)            │
│  → instructor+llm   │        │                      │
│  → diskcache        │        │                      │
│  produces XmlElement│        │  produces XmlElement │
└────────┬────────────┘        └──────────┬───────────┘
         │                                │
         └──────────────┬─────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│              ONE Canonical Pydantic Model            │
│  SurveyModel — populated by both parsers             │
│  XmlElement (discriminated union by tag)             │
│  XmlRadio, XmlCheckbox, XmlText, XmlSelect, ...      │
│  Optional parser_meta field (doc-side annotations)   │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │  Label Normalizer │
            │  (fuzzy matching) │
            └────────┬─────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│          Check Engine (@register_check registry)     │
│  run(xml_side, doc_side) — same type both sides      │
│  Severity levels: ERROR / WARNING / INFO             │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                   Reporters                          │
│   Excel (openpyxl) + Console (rich)                  │
└──────────────────────────────────────────────────────┘
```

---

## Delivery Modes

### Mode 1: CLI / FastAPI (batch and automated use)

```
survey-qa check survey.xml questionnaire.docx --output report.xlsx
```

- Full pipeline runs unattended
- Exit code 1 if errors found (CI/CD compatible)
- FastAPI exposes `POST /qa/compare` for programmatic use
- Suitable for processing multiple surveys, commit hooks, scheduled runs

### Mode 2: MCP Server (interactive use inside Claude)

```
User: "Check this XML against this questionnaire"
Claude: [calls parse_xml(), run_checks(), interprets findings]
Claude: "Found 3 errors. Q7 has a type mismatch — the doc says radio but the XML has checkbox. Here's the fix..."
```

- Claude reads the questionnaire natively — no extraction pipeline needed
- MCP tools expose: `parse_xml()`, `run_checks()`, `generate_report()`
- Claude reasons about findings, explains them, suggests XML edits
- Team members with no terminal access can run full QA through conversation

---

## Design Decisions

### 1. One Unified Model (Not Two)

Both parsers produce **the same Pydantic models**. There is no separate `QuestionnaireModel` or `ParsedQuestion` type. The XML parser produces `XmlRadio`, `XmlCheckbox`, etc.; the doc parser produces the same `XmlRadio`, `XmlCheckbox`, etc.

- `XmlElement` is a **discriminated union** tagged by the `tag` field: `XmlRadio | XmlCheckbox | XmlText | XmlNumber | XmlSelect | XmlFloat | ...`
- Misclassified elements fail at parse time, not silently downstream
- Pydantic v2 provides automatic validation, serialization, and clean error messages

Why one model instead of two:
- Check signatures become `run(xml_side: XmlRadio, doc_side: XmlRadio)` — same type on both sides
- No conversion layer between doc output and check input
- Adding a field once propagates everywhere
- The model is the single source of truth for the schema; parsers fill in what they can

Fields that the doc can't express (e.g. `rowstyle`, `where`, `aggregate`) stay `None` on the doc side. Checks naturally skip them when either side is missing the value.

### 2. Parser Metadata via Optional `parser_meta` Field

Each element type has an optional `parser_meta: ParserMeta | None = None` field for parser-side annotations:

```python
class ParserMeta(BaseModel):
    source: Literal["xml", "doc"]
    confidence: float = 1.0
    source_excerpt: str | None = None      # the text the LLM extracted this from
    ambiguity_notes: list[str] = []        # e.g. "label was guessed from context"
    raw_display_logic: str | None = None   # plain English when cond couldn't be translated
```

- XML parser leaves `parser_meta = None` (or sets `source="xml"` with no other fields)
- Doc parser populates `parser_meta` with confidence, source excerpt, ambiguity notes
- `parser_meta` is **reporter-visible** but **check-invisible** — checks compare semantic fields only

### 3. Three-Stage Doc Parser (Cost Control)

LLM calls are the only meaningful cost in the pipeline. Three stages keep this minimal:

| Stage | Tool | Cost |
|---|---|---|
| Text extraction | `python-docx` / `pdfplumber` | Zero |
| Chunking | Regex heuristics (~6k chars/batch) | Zero |
| LLM extraction | `instructor` + `litellm` | ~$0.005 per 100 questions |

Results are cached by `SHA-256(text + model_name + schema_version)` using `diskcache`. Re-running against the same document costs nothing after the first run. If the model schema changes (e.g. new field added), the schema hash invalidates the cache automatically.

### 4. The `cond` Field

Both parsers populate `cond` with **Decipher syntax** (e.g. `ans(S6,[r1])`, `flt(S8) >= 18`). The doc parser uses the Decipher function library reference (see `07_DECIPHER_FUNCTION_LIBRARY.md`) to translate plain-English display logic from the doc into actual Decipher expressions.

If the doc parser can't produce valid syntax (e.g. ambiguous English, missing label reference), it leaves `cond = None` and stores the raw English in `parser_meta.raw_display_logic`. The condition-matching check fires on that case.

When both sides have valid `cond` expressions, comparison becomes a direct string match (or AST diff) — no LLM-judged semantic equivalence needed.

### 5. XML Parser is Deterministic

The Decipher XML is well-structured. Uses `lxml` — no AI, no cost, no variance. Rules are explicit per element type. HTML is stripped from `<title>` text before comparison.

### 6. instructor + litellm (Not Raw API Calls)

`instructor` wraps LLM calls and enforces Pydantic schema compliance with automatic retries. `litellm` provides provider abstraction — swap between OpenAI, Anthropic, and Ollama via config, not code changes.

This eliminates an entire class of bugs: malformed LLM output triggers a retry, not a crash.

### 7. @register_check Decorator Registry

Checks self-register via decorator — no central dict to maintain:

```python
@register_check
class RA001_RowCount(Check):
    id = "RA-001"
    applies_to = "radio"

    def run(self, xml_side: XmlRadio, doc_side: XmlRadio) -> list[Finding]:
        ...
```

Adding a new check requires one class definition. Zero wiring. The engine discovers all checks at import time.

Note: checks consume the model; they do **not** drive what the doc parser extracts. The doc parser is tied to the model schema, not to the check registry.

### 8. Label Normalization

Real-world questionnaires and XML often use different labeling schemes. A normalizer runs before checks:

1. Exact match
2. Case-insensitive match
3. Strip known prefixes
4. Suffix match
5. Fuzzy match (rapidfuzz ≥ 80%)

Returns `NormalizationResult` with matched/unmatched labels and warnings about fuzzy matches. Now operates on two `SurveyModel` instances (same type both sides).

### 9. GitHub PR Workflow for Check Management

Check changes never go directly to production. The flow:

```
Team member describes change in Claude conversation
    ↓
Claude generates the check class (follows @register_check pattern)
    ↓
GitHub MCP creates branch: checks/add-{check-id}
    ↓
GitHub MCP commits file to checks/, opens PR, adds owner as reviewer
    ↓
Owner reviews generated code → merge or reject
```

This applies to: adding a check, modifying a check's logic or thresholds, disabling or removing a check.

### 10. Severity Levels

| Level | Meaning |
|---|---|
| `ERROR` | Clear mismatch — must be fixed before launch |
| `WARNING` | Likely issue but may be intentional |
| `INFO` | Notable difference worth reviewing |

---

## Canonical Model (Single Source of Truth)

```python
# One discriminated union — both parsers produce these types
XmlElement = Annotated[
    XmlRadio | XmlCheckbox | XmlText | XmlNumber | XmlSelect | XmlFloat | ...,
    Field(discriminator="tag")
]

class ParserMeta(BaseModel):
    source: Literal["xml", "doc"]
    confidence: float = 1.0
    source_excerpt: str | None = None
    ambiguity_notes: list[str] = []
    raw_display_logic: str | None = None

class XmlRow(BaseModel):
    label: str
    text: str
    value: str | None = None
    is_open: bool = False
    is_exclusive: bool = False
    terminate: bool = False
    rowstyle: str | None = None

class XmlRadio(BaseModel):
    tag: Literal["radio"]
    label: str
    title: str
    rows: list[XmlRow]
    cond: str | None = None
    optional: bool = False
    where: str | None = None
    parser_meta: ParserMeta | None = None    # parser annotations; check-invisible

class SurveyModel(BaseModel):
    elements: list[XmlElement]

class Finding(BaseModel):
    check_id: str
    severity: Severity
    question_label: str
    message: str
    detail: str | None = None
```

Fields are optional where the doc parser may not be able to populate them. The XML parser fills in everything it sees in the XML; the doc parser fills in what it can extract from prose.

---

## Report Output

### Excel (primary)
Three sheets:
- **Summary** — count of ERROR / WARNING / INFO, pass/fail per question
- **Findings** — full findings table, color-coded by severity
- **Questions** — all questions from both sides for reference; `parser_meta` shown in a separate column when populated

### Console (rich terminal)
Color-coded table, suitable for CI/CD output.

### JSON (API)
`POST /qa/compare` returns `list[Finding]` serialized via Pydantic.

---

## Related References

- `04_DECIPHER_XML_REFERENCE.md` — XML element reference
- `06_RADIO_ELEMENT_REFERENCE.md` — full radio element attributes
- `07_DECIPHER_FUNCTION_LIBRARY.md` — Decipher function library (`ans`, `flt`, `label`, etc.) — used by the doc parser to translate plain-English logic into `cond` expressions
