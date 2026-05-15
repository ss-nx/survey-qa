# Compact Format — Doc-Side Element Spec

> **Status:** Draft. Several open questions at the bottom. Edit in commits, not chat.

## 1. Motivation

The Skill's first design has Claude author the entire doc-side `SurveyModel` as JSON inside a tool call. For a 57-question survey, that's ~100 KB of structured output and ~12 minutes of sequential token generation. Half the tokens are XML-flavored fields (`id`, `position`, `title_raw`, per-row IDs) that have no meaning on the doc side — they exist because the model was designed XML-first.

We don't need the LLM to generate JSON. LLMs are slow at producing structured syntax but good at three things:

- **Classifying** (this is a radio / checkbox / text / etc.)
- **Extracting text verbatim** (the question title, the option list)
- **Applying rules** (the doc says "specify ___" → mark the row open)

The compact format is plain-text input Claude produces that captures just those three things. A deterministic parser turns the compact text into a typed `XmlElement` using templates per question type.

**Target:** ~5× smaller per-question output, no malformed JSON, no synthetic ID generation, no XML-flavored fields visible to Claude.

## 2. Format overview

One block per survey element. Three regions:

```
## <type>
<title text — one or more lines>
<key>: <value>
options:
  1. <option text>  [tag] [tag]
  2. <option text>
```

List items are always numbered (`N. text`). The number is the option's `value` in the resulting `XmlRow` / `XmlChoice`. If the questionnaire shows codes explicitly (e.g., `99. Refused`), the LLM copies them verbatim; if not, it numbers sequentially `1..N`. This applies to `options:`, `rows:`, `cols:`, and `choices:`.

- **Header line.** `## <type>` or `## <type> [label]` — see §5 on labels.
- **Free-text body.** Lines between the header and the first key/list line are the title.
- **Keys and lists.** Recognized keys: `flags`, `atleast`, `display`, `options`, `choices`, `rows`, `cols`, `target`, `sheet`, `overquota`, `term`, `note`.

A blank line separates blocks. Order of elements in the compact stream determines order in the assembled `SurveyModel`.

### Text formatting and inline structure

The compact parser stores text verbatim; any inline HTML survives untouched. The format uses HTML conventions to match what the XML side carries in `title_raw` / option `text`:

- Character formatting: `<b>...</b>`, `<i>...</i>`, `<u>...</u>` (nested allowed)
- Visible line break within a title or option: `<br>`
- Inline list within a title or option: `<ul><li>...</li>...</ul>` (or `<ol>`)

Color is ignored. This convention removes the need for a markdown↔HTML normalization layer in text-equality checks, and preserves visible structure that would otherwise be lost when extractors strip paragraph breaks.

## 3. Question types

### Radio (single-select)

```
## radio
Where do you live?
options:
  1. United States
  2. Canada
  3. United Kingdom
  98. Other, please specify  [open]
  99. I prefer not to answer  [exclusive]
```

Row-level termination uses the block-level `term:` key (see §3 ▸ Termination):

```
## radio
What is your age?
term: r4
options:
  1. 18-24
  2. 25-34
  3. 35-44
  4. Under 18
```

### Checkbox (multi-select)

```
## checkbox
Which streaming services do you subscribe to?
options:
  1. Netflix
  2. Hulu
  3. Disney+
  4. HBO Max
  99. None of the above  [exclusive]
```

`atleast: N` only when the doc states a non-default minimum.

### Text (open-end)

```
## text
Please describe your experience with our customer service.
flags: optional
```

### Number / Float

```
## number
How many people live in your household?
```

```
## float
What percentage of your time is spent remote?
```

### Select (dropdown)

```
## select
State of residence
choices:
  1. Alabama
  2. Alaska
  3. ... (one per line)
```

### HTML (display-only)

```
## html
Welcome to the survey. Please answer all questions as accurately as you can.
```

### Term (termination)

```
## term
Sorry, you must be 18 or older to participate.
display: if Q1 < 18
```

Row- and cell-level terminations live on the question itself via the block-level `term:` key (see Termination below). Use a standalone `## term` block only when the doc describes a separate termination condition, independent of any specific question's options.

### Termination (`term:` key)

Block-level `term:` on a `radio`, `checkbox`, or `text` block expresses a termination condition over the question's rows/cols/cells. The expression grammar:

```
expr      := term ("or" term)*
term      := factor ("and" factor)*
factor    := "not"? (coord | "(" expr ")")
coord     := "r" N ("." "c" M)? | "c" N
```

Plus: commas at the top level are shorthand for `or`. So `r1.c5, r2.c5` is `r1.c5 or r2.c5`.

Examples:

- `r4` — single row terminates
- `r1.c5, r2.c5` — grid: either cell terminates ("Hate it" for Apple or Samsung)
- `r3 and r4` — checkbox: both selected terminates
- `not r1` — anything except r1 terminates
- `(r3 and r4) or r5` — either pattern terminates

The compact parser tokenizes and validates that every non-keyword token is a well-formed coordinate. It does NOT build a parse tree or evaluate semantics. The full expression is stored verbatim in `parser_meta.ambiguity_notes` because `XmlRow` has no `is_terminate` field today. Promoting termination to a first-class field — and reusing this grammar in a check that compares against XML-side `<term cond="...">` — is logged as Open question O-8.

Example: a brand-rating grid where "Hate it" (column 5) for any brand screens out:

```
## radio
Rate each brand.
term: r1.c5, r2.c5
cols:
  1. Love it
  2. Like it
  3. Neutral
  4. Dislike it
  5. Hate it
rows:
  1. Apple
  2. Samsung
```

### Quota

```
## quota
sheet: Age Quotas
overquota: term_overquota
```

### Goto (routing jump)

```
## goto
target: end
display: if S1 = "no"
```

### ~~Suspend~~ (removed from doc-side)

The compact format does not include suspends. Page-break placement is an XML-side concern and is audited by RO-004 against the XML alone. See Decisions log.

## 4. The defaults principle

**Only emit a key when its value differs from the default.** Silence means standard.

| Field | Default | Emit when |
|---|---|---|
| `flags: optional` | required | Doc explicitly says optional |
| `atleast: N` | 1 (checkbox) | Doc states a different minimum |
| `display: ...` | none | Doc has a routing/display note |
| `[open]` tag on row | not open | Doc has "specify ___" / "Other ___" |
| `[exclusive]` tag on row | not exclusive | Doc marks "None of the above" / "Prefer not to say" / similar |
| `term: rN, rN.cM, cN, ...` | nothing terminates | Doc marks rows / cols / cells as screen-outs |

Every line Claude writes should answer "what does this doc say that's different from a standard required question?" If everything's standard, the block is just header + title + options.

## 5. Label handling

**Use the QNR's label when shown. Omit when not.**

When the questionnaire document explicitly labels a question (e.g., "S1.", "Q1:", "Awareness_Q1"), Claude includes it in the compact header:

```
## radio [S1]
Where do you live?
```

The compact parser uses that label directly (`label="S1"`, `id="doc:S1"`) and the normalizer's existing label-based strategies (exact / case-insensitive / prefix-strip / suffix / fuzzy) bind it to the matching XML question. This is the most reliable binding path.

When the QNR does NOT show a label, Claude omits the bracket:

```
## radio
Where do you live?
```

The parser assigns a synthetic label (`doc:q1`, `doc:q2`, ... in document order). The normalizer detects the `doc:` prefix, skips label strategies, and falls back to **title-similarity matching** against XML question titles. The strategies are applied in this order:

  1. Exact match             — Q1 == Q1
  2. Case-insensitive        — q1 == Q1
  3. Strip common prefixes   — "question_Q1" → "Q1"
  4. Suffix match            — "Awareness_Q1" ends with "Q1"
  5. Fuzzy label match       — rapidfuzz token_sort_ratio (≥ threshold)
  6. Title-similarity match  — applies only when the doc label starts with
                                `doc:` (the synthetic-label sentinel). Same
                                algorithm as step 5 but on question titles,
                                with the tag-equality and minimum-score
                                guardrails below.

### Tiebreaker rules for title similarity

To prevent two doc questions with similar titles from being mis-bound:

- Require the matched XML question to have the same `tag` (radio↔radio, checkbox↔checkbox, etc.)
- Require title similarity ≥ 80% (rapidfuzz `token_sort_ratio`)
- If multiple XML questions tie within 5 points, prefer the unmatched one earliest in document order

## 6. Normalizer change

Current strategies (run in order, first match wins):

1. Exact label match
2. Case-insensitive
3. Strip common prefixes
4. Suffix match
5. Fuzzy label match (rapidfuzz, threshold 80)

Add:

6. **Title similarity match** — same algorithm as step 5 but applied to `question.title` against XML `q.title`, with the tag-equality and minimum-score guardrails above.

When step 6 fires, emit a warning into `NormalizationResult.warnings` like:

> Title-similarity match (87%): "Where do you live?" → XML label "screen_country"

So humans reviewing the report can audit the binding.

## 7. Parser contract

New module: `survey_qa/doc_parser/compact_parser.py`

```python
def parse_compact(text: str) -> SurveyModel:
    """Parse a compact-format document into a doc-side SurveyModel.

    Each block becomes an XmlElement with synthetic id/position/label
    and parser_meta.source = "doc". Auto-generates row labels (r1, r2, ...)
    and row IDs.
    """
```

Templates live in the module itself — one Python function per question type that takes the parsed compact fields and returns the appropriate `XmlElement` subclass with sensible defaults.

The compact parser must:
- Be deterministic (no LLM)
- Validate against `SurveyModel` (raise `CompactParseError` on malformed input)
- Populate `parser_meta` with `source="doc"`, `confidence=1.0` for cleanly-parsed blocks
- For blocks with unrecognized keys, preserve them in `parser_meta.ambiguity_notes`
- Never invent semantic content — only structural defaults

## 8. Edge cases

### Grid questions

A grid radio or checkbox has both `rows` and `cols`:

```
## radio
For each brand, rate your overall opinion.
cols:
  1. Very unfavorable
  2. Somewhat unfavorable
  3. Neutral
  4. Somewhat favorable
  5. Very favorable
rows:
  1. Apple
  2. Samsung
  3. Google
```

Text grids similarly:

```
## text
For each item, write a one-sentence reaction.
rows:
  1. Customer service
  2. Product quality
  3. Price
```

### Multi-line option text

Each option must be one line. If the doc wraps an option across lines, Claude should join them into a single line. The format does not support multi-line options. // OPEN: revisit if real-world surveys break this assumption.

### Ambiguous content

If a chunk of the doc doesn't fit any question type (programmer notes, section dividers, raw HTML), Claude emits:

```
## html
<whatever the text was>
```

It's preserved in the model as a display-only element. The `tag="html"` lets reporters flag it as "not a respondent-facing question, kept for context."

### Conditions / display logic

`display:` accepts plain English. Phase 4 (separate work) introduces an AST diff against Decipher syntax. For now the doc-side `display:` value is preserved as-is in `parser_meta.raw_display_logic`. The compact parser does not attempt to translate plain English into Decipher syntax.

### Empty doc

A compact stream with no `##` blocks parses to a `SurveyModel` with an empty `elements` list. The normalizer + checks handle this gracefully (every XML question fires Q-001 "not found in doc").

## 9. Open questions

### O-1. Should Claude be able to mark uncertainty inline?

When Claude isn't sure about a question — say, the doc has unusual structure or contradictory instructions — should the format support a per-block confidence/note tag?

```
## radio
What is your favorite color?
note: doc lists options inline in a paragraph; I parsed them but order may be wrong
options:
  1. Red
  2. Blue
  3. Green
```

The `note:` would land in `parser_meta.ambiguity_notes` and surface in the Excel report's questions sheet. **Proposed default: yes, support `note:` lines.** Open for objection.

### O-2. ~~Should row codes ever come from the doc?~~ — resolved

Resolved by making all list items numbered (`N. text`). The number IS the row's `value`. Claude copies the questionnaire's codes verbatim when shown, or numbers sequentially when not. See Decisions log.

### O-3. Should we support an alternate "rows" syntax for short option lists?

For a yes/no question, the compact form has more boilerplate than content:

```
## radio
Have you visited our website?
options:
  1. Yes
  2. No
```

vs.

```
## radio (yes/no)
Have you visited our website?
```

The `(yes/no)` shortcut would expand to a standard Yes/No options pair. **Proposed default: no — keep the format predictable, even if a tiny bit more verbose.** Open.

### O-4. Suspend handling — explicit or inferred?

Decipher requires a `<suspend/>` between questions to separate pages. The doc rarely calls these out explicitly. Options:

- **Always require `## suspend` between blocks** — verbose, but matches XML faithfully.
- **Auto-insert suspends between every two question blocks** — silent, but might over-page.
- **Only emit suspends when doc says "page break" / "end of section"** — relies on doc convention.

**Proposed default:** don't emit suspends from the doc side at all. RO-004 checks XML-side suspend placement; the doc side doesn't need to assert page boundaries. Open.

### O-5. Should the compact stream end with a marker?

For long streams, an explicit `## END` block helps detect truncation. **Proposed default: no, parse to EOF. Add later if truncation becomes a real problem.** Open.

### O-6. Title-similarity threshold

§5 proposes a similarity threshold of 80% with a 5-point tiebreaker margin. Both numbers are guesses. We'll know better numbers once we test against a real questionnaire. **Action item:** treat 80/5 as the starting point; tune after measuring false positives/negatives on the MTM survey.

### O-7. ~~Markdown-to-HTML formatting normalization~~ — resolved

Resolved by using HTML tags (`<b>`, `<i>`, `<u>`) on the doc side, matching the XML side directly. See Decisions log.

### O-8. Promote `[term]` / grid terminations to a first-class model field

Today the compact parser stores `term:` coordinates as text in `parser_meta.ambiguity_notes`. This means termination checks can't programmatically verify that the XML side correctly maps "row 4 of Q1" to a `<term cond="Q1.r4 == 1">` block. To do that, we'd need:

- `XmlRow.is_terminate: bool` (and possibly `XmlCol.is_terminate: bool`)
- A `XmlQuestion.terminating_cells: list[tuple[int, int]]` for grids
- The XML parser populates these by walking `<term>` conds and resolving label/row references
- The compact parser populates these from the parsed `term:` coordinates
- A new check (e.g., RO-006) verifies the two sides match

**Proposed default:** model change is in scope but not blocking the MVP. Ship the doc-side capture first; add the field + check in a follow-up. Open.

---

## Decisions log

- **2026-05-16 — Resolved O-4 (suspend handling):** doc-side compact format does NOT emit `## suspend` blocks. Page-break placement is an XML-side concern audited by RO-004. The compact parser rejects `## suspend` as an unknown type.
- **2026-05-16 — Replaced `[terminate]` row tag with block-level `term:` key.** Rationale: grids need to express cell-level termination (`r1.c5`) which a per-row tag cannot capture. One syntax for flat and grid questions reduces cognitive load. Standalone `## term` blocks are unchanged.
- **2026-05-16 — Text formatting is preserved using HTML tags** (`<b>`, `<i>`, `<u>`); color is ignored unless requested. Matches the XML side directly so no normalization layer is needed (resolves O-7).
- **2026-05-16 — List items are always numbered (`N. text`); the `- ` bullet form is removed.** The number IS the option's `value`. Claude copies questionnaire codes verbatim when shown (e.g., `99. Refused`), or numbers `1..N` sequentially when not. One uniform syntax for `options:` / `rows:` / `cols:` / `choices:`. Value-comparison checks (RA-005, RA-006) now work on the doc side without an opt-in (resolves O-2).

## References

- [`STALE_02_ARCHITECTURE.md`](STALE_02_ARCHITECTURE.md) — canonical model (pending refresh; still accurate for the model itself)
- [`05_CODING_CONVENTIONS.md`](05_CODING_CONVENTIONS.md) — how checks consume the model
- [`survey_qa/doc_parser/normalizer.py`](../src/survey_qa/doc_parser/normalizer.py) — existing label normalizer
- [`survey_qa/doc_parser/chunker.py`](../src/survey_qa/doc_parser/chunker.py) — existing text chunker (will feed the compact stream)
