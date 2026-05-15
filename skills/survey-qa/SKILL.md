---
name: survey-qa
description: Quality-check a Forsta Decipher survey before launch. Use whenever the user uploads a Decipher XML survey script alongside a client questionnaire document (.docx or .pdf), or asks to "QA a survey", "check this XML against the questionnaire", "find discrepancies between XML and the survey doc", or similar. The skill parses both files, runs structural checks (question types, options, routing, conditions), and surfaces every mismatch — missing options, wrong values, mistyped titles, broken routing, missing terminations.
---

# Survey QA

You are running a survey QA workflow. The user has (or is about to upload) two files:

1. A **Decipher XML** survey script (`.xml`) — the actual programming
2. A **questionnaire document** (`.docx` or `.pdf`) — the source of truth

Your job: compare them, identify every place the XML doesn't match the questionnaire, and produce a clear report.

## What this skill provides

A bundled Python package (`survey_qa/`) and entry-point scripts under `scripts/`:

| Script | What it does |
|---|---|
| `parse_xml.py <xml_path>` | Parse Decipher XML → SurveyModel JSON on stdout |
| `extract_doc_text.py <doc_path>` | Extract plain text from .docx or .pdf → stdout |
| `parse_compact.py <compact_path>` | Parse compact-format doc text → SurveyModel JSON on stdout |
| `run_checks.py <xml_path> <doc_survey_json_path>` | Run all QA checks → findings JSON on stdout |
| `make_report.py <xml_path> <findings_json_path> <out_path.xlsx>` | Write color-coded Excel report |

The check engine, models, and parsers are pure-Python and live in `survey_qa/`.

## Workflow

1. **Locate both files** the user uploaded (Decipher .xml and questionnaire .docx/.pdf).

2. **Parse the XML.** Run `python scripts/parse_xml.py <xml_path>`. You'll get a SurveyModel JSON describing every question, option, term, quota, suspend, and goto in the XML.

3. **Extract the questionnaire text.** Run `python scripts/extract_doc_text.py <doc_path>`. You'll get the plain text of the document.

4. **Author a compact-format stream.** Read the extracted text and write one block per survey element using the format below. Save the result to a temp file (e.g. `/tmp/doc.compact.txt`).

5. **Parse the compact stream.** Run `python scripts/parse_compact.py <compact_path>` to convert it to a doc-side SurveyModel JSON. Save to a temp file.

6. **Run the checks.** `python scripts/run_checks.py <xml_path> <doc_survey_json_path>`. You'll get findings with severity (error / warning / info), check_id, question_label, and a human message.

7. **Present the findings to the user.** Group by severity. Errors first. Be specific — quote the XML vs the doc when they mismatch. Suggest fixes.

8. **Optional: write an Excel report.** If the user wants a downloadable report (or there are more than 20 findings), call `python scripts/make_report.py <xml_path> <findings_json> <output.xlsx>` and offer the file.

## Compact format

One block per survey element. Three regions:

```
## <type>
<title text — one or more lines>
<key>: <value>
options:
  1. <option text>  [tag] [tag]
  2. <option text>
```

- **Header line.** `## <type>` or `## <type> [label]` — see Labels below.
- **Free-text body.** Lines between the header and the first key/list line are the title.
- **Keys and lists.** Recognized keys: `flags`, `atleast`, `display`, `options`, `choices`, `rows`, `cols`, `target`, `sheet`, `overquota`, `term`, `note`.

A blank line separates blocks. Order of blocks determines order in the SurveyModel.

### Option numbering — match the screener

List items are **always** numbered (`N. text`) — no `- ` bullets.

- **If the questionnaire shows codes** (e.g., `1. USA`, `2. Canada`, `99. Refused`), copy them verbatim. Decipher uses these as `value=` on the option, and value-comparison checks depend on it.
- **If the questionnaire doesn't show codes**, number sequentially `1, 2, 3, ...`.
- This applies to `options:`, `rows:`, `cols:`, and `choices:` — same rule everywhere.

### Text formatting and structure

**Preserve the doc's character formatting AND visible structure using HTML tags.** The XML side carries these as inline HTML in `title_raw` and option text. Matching the convention on the doc side makes text-equality checks work cleanly.

**Character formatting:**
- Bold → `<b>text</b>`
- Italic → `<i>text</i>`
- Underline → `<u>text</u>`
- Nested formatting is fine: `<b><i>text</i></b>`.
- **Ignore color** (font color, highlights) unless the user specifically asks you to track it.

**Structure within a title or option text:**
- Visible line break → `<br>`
- Inline bullet list → `<ul><li>first</li><li>second</li></ul>`
- Inline numbered list → `<ol><li>first</li><li>second</li></ol>`

Apply these in both titles AND option text. Don't add formatting or structure the doc didn't have.

If an option's text in the doc spans multiple visual lines with an intentional break, use `<br>` inside it — keep one option per compact-format line. Example:

```
options:
  1. Short option
  2. Long option<br>with a forced visual break
```

### The defaults principle

**Only emit a key when its value differs from the default.** Silence means standard.

| Field | Default | Emit when |
|---|---|---|
| `flags: optional` | required | Doc explicitly says optional |
| `atleast: N` | 1 (checkbox) | Doc states a different minimum |
| `display: ...` | none | Doc has a routing/display note |
| `[open]` tag on row | not open | Doc has "specify ___" / "Other ___" |
| `[exclusive]` tag on row | not exclusive | Doc marks "None of the above" / "Prefer not to say" / similar |
| `term: r1, r2.c3, ...` | nothing terminates | Doc marks one or more rows/cols/cells as screen-outs |

If everything's standard, a block is just header + title + options.

### Labels — copy from QNR when shown, otherwise omit

If the questionnaire labels a question explicitly (e.g., "S1.", "Q1:", "Awareness_Q1"), include it in the header in square brackets:

```
## radio [S1]
Where do you live?
options:
  1. United States
  2. Canada
```

When the doc shows a label, the normalizer uses it directly with exact / case-insensitive / prefix-strip / suffix / fuzzy label matching against the XML labels. This is the most reliable binding.

If the questionnaire does NOT show a label for a question, omit the bracket entirely:

```
## radio
Where do you live?
options:
  1. United States
  2. Canada
```

The parser assigns a synthetic label (`doc:q1`, `doc:q2`, ...) in document order. The normalizer then falls back to title-similarity matching to bind it to an XML question.

**Don't invent labels.** If the doc doesn't show one, leave it out. Inventing makes binding less reliable, not more.

## Type templates

### radio — single-select

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

Codes 98/99 in the example come from the questionnaire — copy whatever the doc shows. If the doc doesn't specify codes, just use `1, 2, 3, ...` sequentially.

If a row terminates the respondent, add a block-level `term:` key with the row coordinate (`r4` = the 4th option, by position not code):

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

Compound termination conditions use `and` / `or` / `not` and parens. Comma is a shorthand for OR.

- `term: r4` — single row
- `term: r1, r2` — either row (same as `r1 or r2`)
- `term: r3 and r4` — both rows selected (only meaningful for checkbox)
- `term: not r1` — anything except r1
- `term: (r1 and r2) or r3` — mixed

Only coordinates (`rN`, `rN.cM`, `cN`), `and`/`or`/`not`, commas, and parens are allowed. Anything else (label references, value comparisons, etc.) belongs in a standalone `## term` block with `display:`.

### checkbox — multi-select

```
## checkbox
Which streaming services do you subscribe to?
options:
  1. Netflix
  2. Hulu
  3. Disney+
  99. None of the above  [exclusive]
```

Add `atleast: N` only when the doc states a non-default minimum.

### text — open-end

```
## text
Please describe your experience with our customer service.
flags: optional
```

### number — integer input

```
## number
How many people live in your household?
```

### float — decimal input

```
## float
What percentage of your time is spent remote?
```

### select — dropdown

```
## select
State of residence
choices:
  1. Alabama
  2. Alaska
  3. ... (one per line)
```

### html — display-only / non-question content

```
## html
Welcome to the survey. Please answer all questions as accurately as you can.
```

Also use `html` for any content that doesn't fit another type (programmer notes, section dividers, raw HTML preserved for context).

### term — termination

```
## term
Sorry, you must be 18 or older to participate.
display: if Q1 < 18
```

Most terminations are row- or cell-level — express those with the block-level `term:` key on the question itself (see the radio example above and the Grids section below). Use a standalone `## term` block only when the doc describes a separate termination condition independent of any specific question's options.

### quota

```
## quota
sheet: Age Quotas
overquota: term_overquota
```

### goto — routing jump

```
## goto
target: end
display: if S1 = "no"
```

> Note: doc-side output does NOT emit `suspend` blocks. Page-break placement is an XML-side concern; the routing checks audit XML suspends directly.

## Grids

A grid has both `rows:` and `cols:`. Works for `radio`, `checkbox`, and `text`:

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

If specific cells terminate the respondent, use the `term:` key with `rN.cM` coordinates. Coordinates are positional (`r1` = first row in the list, regardless of explicit codes):

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

`term:` accepts coordinates (`rN`, `rN.cM`, `cN`) combined with `and` / `or` / `not` and parens. Commas are shorthand for OR. See the radio section above for the full syntax.

## Important rules

- **The questionnaire is the source of truth.** When the XML and the doc disagree, the doc wins. Phrase findings as "XML should match the questionnaire."
- **Don't over-summarize.** If there are 30 errors, list all 30 (perhaps grouped by question).
- **One option per line.** If the doc wraps an option across lines, join them.
- **Don't invent content.** If a question's options are unclear, write what you can and add a `note:` line; it lands in `parser_meta.ambiguity_notes` for the report.
- **If the XML parser fails** (malformed XML), say so and stop. Don't try to continue.
- **`display:` accepts plain English.** Don't try to translate into Decipher syntax — the parser preserves it as-is.
