# Survey QA Tool — Coding Conventions & Extensibility Guide

## Purpose

This file tells any developer (or AI assistant) how to add new checks, parsers, or question types to the QA tool without breaking existing behaviour.

---

## Models: One Unified Pydantic v2 Schema

There is **one canonical model** — the `XmlElement` family. Both the XML parser and the doc parser produce instances of the **same types** (`XmlRadio`, `XmlCheckbox`, `XmlText`, etc.).

**Do not** create a separate `ParsedQuestion` / `QuestionnaireModel` type. **Do not** use plain `@dataclass`.

```python
# CORRECT — one model, both parsers fill it in
from pydantic import BaseModel, Field
from typing import Annotated, Literal

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
    parser_meta: ParserMeta | None = None  # parser annotations; check-invisible

XmlElement = Annotated[
    XmlRadio | XmlCheckbox | XmlText | XmlNumber | XmlSelect | XmlFloat,
    Field(discriminator="tag")
]

class SurveyModel(BaseModel):
    elements: list[XmlElement]
```

The discriminator (`tag`) means misclassified elements fail at parse time, not silently downstream.

---

## Parser Metadata: The `parser_meta` Field

Each element has an optional `parser_meta: ParserMeta | None = None` field. This is where parser-side annotations go — confidence, source excerpt, ambiguity notes.

```python
class ParserMeta(BaseModel):
    source: Literal["xml", "doc"]
    confidence: float = 1.0
    source_excerpt: str | None = None
    ambiguity_notes: list[str] = []
    raw_display_logic: str | None = None
```

**Rules**:
- The XML parser leaves `parser_meta = None` (or sets `source="xml"` with nothing else).
- The doc parser populates `parser_meta` with confidence and any caveats.
- **Checks ignore `parser_meta`** — it is not part of the semantic comparison.
- **Reporters can read `parser_meta`** — surface it when relevant (e.g. "this question's label was guessed").

If the doc parser can't translate plain-English display logic into a valid `cond` expression, it leaves `cond = None` and stores the raw English in `parser_meta.raw_display_logic`.

---

## Doc Parser Contract

The doc parser is tied to the **model schema**, not to the check registry.

- Accept a file path (`.docx` or `.pdf`)
- Extract plain text via `python-docx` / `pdfplumber`
- Chunk into question-candidate batches
- Call LLM via `instructor` + `litellm` with the unified Pydantic schema as the response model
- Populate every field it can extract from the source text
- Leave fields it can't extract as `None`
- Populate `parser_meta` with confidence, source excerpt, and any ambiguity notes
- Translate plain-English display logic into Decipher syntax for `cond`, using `07_DECIPHER_FUNCTION_LIBRARY.md` as the reference for valid functions (`ans`, `flt`, `label`, etc.)
- Cache results by `SHA-256(text + model_name + schema_version)` — schema changes invalidate the cache automatically
- Raise `DocParseError` with a clear message if extraction fails

The doc parser must not consult the check registry. Checks consume the model; they do not drive extraction.

---

## XML Parser Contract

- Accept a file path (`.xml`)
- Parse deterministically using `lxml`
- Produce instances of the unified `XmlElement` types
- Skip non-question structural elements where appropriate (`<suspend/>`, `<condition>`, `<quota>`, `<html>`, elements with `where="execute"` only)
- Strip HTML tags from `<title>` text
- Leave `parser_meta = None`
- Raise `XMLParseError` with a clear message if the file is malformed

The XML parser must never call an LLM. It is deterministic by design.

---

## Adding a New Check

Checks live in `survey_qa/checks/`. Each check is a class that inherits from `Check` and uses the `@register_check` decorator.

### Step 1 — Write the class

```python
# survey_qa/checks/radio_checks.py

from survey_qa.checks import register_check, Check
from survey_qa.core.models import XmlRadio, Finding, Severity

@register_check
class RA007_MaxOptionCount(Check):
    id = "RA-007"
    description = "Radio questions should not exceed 15 options"
    applies_to = "radio"

    def run(self, xml_side: XmlRadio, doc_side: XmlRadio) -> list[Finding]:
        if len(xml_side.rows) > 15:
            return [Finding(
                check_id=self.id,
                severity=Severity.WARNING,
                question_label=xml_side.label,
                message=f"Radio question has {len(xml_side.rows)} options (max recommended: 15)",
                detail=None,
            )]
        return []
```

Note the signature: **both parameters are the same type** (`XmlRadio` here). The `xml_side` is what the XML parser produced; the `doc_side` is what the doc parser produced. They are the same Pydantic class.

### Step 2 — That's it

The `@register_check` decorator adds the class to the global registry automatically. No changes needed to `check_engine.py` or any other file. The engine discovers all checks at import time.

**Do not** maintain a manual dict of checks. **Do not** modify `run_checks()` to add new checks.

---

## Handling Missing Fields in Checks

Because the doc parser may not be able to extract every field, checks must handle `None` gracefully:

```python
def run(self, xml_side: XmlRadio, doc_side: XmlRadio) -> list[Finding]:
    # Skip the check if the doc didn't provide this field
    if doc_side.cond is None:
        return []
    if xml_side.cond != doc_side.cond:
        return [Finding(...)]
    return []
```

Fields that exist in the XML but have no doc equivalent (`rowstyle`, `where`, `aggregate`) will be `None` on the doc side. Checks targeting those fields should only fire when both sides have values, unless the check is explicitly about XML-only behaviour.

---

## Check Management via GitHub PR

**Checks never go directly to production.** Any addition, modification, or removal of a check must go through the GitHub PR workflow:

1. Describe the change in a Claude conversation
2. Claude generates the check class following this pattern
3. GitHub MCP creates a branch (`checks/add-{id}`, `checks/modify-{id}`, `checks/remove-{id}`)
4. GitHub MCP commits the change and opens a PR
5. Owner reviews → merge or reject

This applies even to small changes like updating a severity level or adjusting a fuzzy match threshold.

---

## Adding a New Question Type

### Step 1 — Add the Pydantic model

```python
# survey_qa/core/models/elements.py (or wherever your models live)

class XmlRanking(BaseModel):
    tag: Literal["ranking"]
    label: str
    title: str
    rows: list[XmlRow]
    cond: str | None = None
    rank_max: int | None = None
    parser_meta: ParserMeta | None = None

# Add to the discriminated union:
XmlElement = Annotated[
    XmlRadio | XmlCheckbox | XmlText | XmlRanking | ...,
    Field(discriminator="tag")
]
```

### Step 2 — Add to the XML parser

```python
QUESTION_TAGS = {"radio", "checkbox", "text", "number", "select", "float", "ranking"}

def _parse_ranking(self, elem) -> XmlRanking:
    return XmlRanking(
        tag="ranking",
        label=elem.get("label"),
        title=strip_html(elem.findtext("title", "")),
        rows=self._parse_rows(elem),
        rank_max=int(elem.get("rankmax")) if elem.get("rankmax") else None,
    )
```

### Step 3 — Update the doc parser prompt

The doc parser uses the model schema as the response model — `instructor` automatically picks up the new type. The system prompt should reference the new question type so the LLM knows what to extract.

### Step 4 — Write checks for the new type

```python
@register_check
class RK001_RankCount(Check):
    id = "RK-001"
    applies_to = "ranking"

    def run(self, xml_side: XmlRanking, doc_side: XmlRanking) -> list[Finding]:
        ...
```

---

## The Finding Model

```python
class Finding(BaseModel):
    check_id: str          # e.g. "RA-001"
    severity: Severity     # ERROR | WARNING | INFO
    question_label: str    # e.g. "S7"
    message: str           # human-readable one-liner
    detail: str | None = None
```

Always populate `message` with a complete sentence. `detail` is optional and used for longer explanations or diffs.

---

## The Severity Enum

```python
from enum import Enum

class Severity(str, Enum):
    ERROR   = "ERROR"    # Must fix before launch
    WARNING = "WARNING"  # Likely issue, review required
    INFO    = "INFO"     # Notable, may be intentional
```

Use `str, Enum` (not just `Enum`) so Pydantic serializes it as a plain string in JSON and Excel output.

---

## LLM Calls: instructor + litellm

The doc parser uses `instructor` to enforce schema compliance and `litellm` for provider abstraction. Do not call the Claude or OpenAI API directly.

```python
# CORRECT
import instructor
import litellm

client = instructor.from_litellm(litellm.completion)
result = client.chat.completions.create(
    model=model_name,
    response_model=SurveyModel,    # the unified model
    messages=[...],
    max_retries=3,
)

# WRONG — bypasses schema enforcement and retry logic
import anthropic
response = anthropic.Anthropic().messages.create(...)
json.loads(response.content[0].text)
```

The LLM prompt and the Decipher function library reference (for translating `cond` expressions) live in `prompts/doc_parser_prompt.txt` and `07_DECIPHER_FUNCTION_LIBRARY.md` respectively.

---

## Caching: Always Cache LLM Results

All LLM calls must be cached using `diskcache` keyed by `SHA-256(input_text + model_name + schema_version)`. The schema version is critical — if the unified model changes, cached extractions become stale and must be regenerated.

```python
import hashlib
import diskcache

cache = diskcache.Cache(".cache/llm")

def extract_with_cache(text: str, model: str, schema_version: str) -> SurveyModel:
    key = hashlib.sha256(f"{text}|{model}|{schema_version}".encode()).hexdigest()
    if key in cache:
        return cache[key]
    result = _call_llm(text, model)
    cache[key] = result
    return result
```

Re-running against the same document with the same schema must cost $0. Never skip caching to "get fresh results" unless explicitly debugging.

---

## Label Normalization: Never Skip It

Before running checks, always call `normalize_labels()`. Since both sides are now the same `SurveyModel` type, the signature is symmetric:

```python
from survey_qa.doc_parser.normalizer import normalize_labels

xml_model = xml_parser.parse(xml_path)
doc_model = doc_parser.parse(doc_path)

norm = normalize_labels(xml_model, doc_model)
doc_model = norm.aligned_model
```

Skipping this step produces false errors when the XML and doc use different labeling schemes.

---

## Fuzzy Matching

Use `rapidfuzz.fuzz.token_sort_ratio` for all text comparisons. The standard thresholds:

| Use case | Threshold |
|---|---|
| Question title match | 90% |
| Option text match | 90% |
| Label normalization | 80% |

Do not use `fuzz.ratio` (order-sensitive) or `fuzz.partial_ratio` (substring-sensitive) for question/option text. `token_sort_ratio` handles word-order variations correctly.

---

## Check Engine Contract

The engine in `survey_qa/checks/__init__.py`:

1. Matches elements on both sides by label (after normalization)
2. For unmatched doc elements → fires Q-001 ERROR
3. For unmatched XML elements → fires INFO
4. For matched pairs → instantiates and runs all registered checks where `applies_to` matches the element's `tag`
5. Handles check errors gracefully — a failing check produces an INFO finding, not a crash

---

## MCP Tools Contract (Phase 5)

MCP tools in `survey_qa/mcp/tools.py` must:

- Accept file paths as strings (MCP serializes everything as JSON)
- Return structured data as dicts (serialized from Pydantic models via `.model_dump()`)
- Never mutate files unless the tool name makes clear it writes output (e.g. `generate_report`)
- Handle errors by returning a structured error dict, not raising exceptions

```python
def parse_xml(file_path: str) -> dict:
    try:
        survey = SurveyParser().parse(file_path)
        return {"ok": True, "survey": survey.model_dump()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

In MCP mode, Claude reads the questionnaire natively — `parse_doc` is not needed. The MCP server only exposes `parse_xml`, `run_checks`, `generate_report`, and `list_checks`.

---

## Testing Conventions

- Unit tests in `tests/`
- Use `pytest`
- No real LLM calls in tests — all checks tested against hand-crafted Pydantic objects
- Use factory helpers (`make_radio()`, `make_row()`, `make_meta()`) for readable tests
- Each check must have at least one passing test and one failing test
- Tests must cover the `None`-on-doc-side case for fields that may not be extractable

```python
def test_ra007_passes_under_limit():
    xml_side = make_radio("Q1", rows=[make_row(f"r{i}") for i in range(10)])
    doc_side = make_radio("Q1", rows=[make_row(f"r{i}") for i in range(10)])
    assert RA007_MaxOptionCount().run(xml_side, doc_side) == []

def test_ra007_warns_over_limit():
    xml_side = make_radio("Q1", rows=[make_row(f"r{i}") for i in range(16)])
    doc_side = make_radio("Q1", rows=[make_row(f"r{i}") for i in range(16)])
    findings = RA007_MaxOptionCount().run(xml_side, doc_side)
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARNING
```

---

## AI Assistant Notes

When working on this codebase:

- **One model, both parsers** — there is no `ParsedQuestion` or `QuestionnaireModel`. Doc parser produces `XmlRadio`, `XmlCheckbox`, etc.
- **Check signatures are symmetric** — `run(xml_side: XmlRadio, doc_side: XmlRadio)`. Same type on both sides.
- **Doc parser is tied to the model**, not to the check registry. Never read the check registry from the doc parser.
- **`parser_meta` is parser metadata** — checks ignore it; reporters surface it.
- **Cache LLM results** — always. Include `schema_version` in the cache key.
- **XML parser is deterministic** — never introduce LLM calls into it.
- **Always normalize labels** before running checks.
- **New checks go through GitHub PR** — generate the code but do not commit directly.
- **Phase scope is in `03_BUILD_PLAN.md`** — don't implement Phase 5+ features in earlier phases.
- **Decipher function library** is in `07_DECIPHER_FUNCTION_LIBRARY.md` — used by the doc parser to translate `cond` expressions from English to Decipher syntax.
