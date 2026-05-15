---
name: survey-qa
description: Quality-check a Forsta Decipher survey before launch. Use whenever the user uploads a Decipher XML survey script alongside a client questionnaire document (.docx or .pdf), or asks to "QA a survey", "check this XML against the questionnaire", "find discrepancies between XML and the survey doc", or similar. The skill parses both files, runs 26 structural checks (question types, options, routing, conditions), and surfaces every mismatch — missing options, wrong values, mistyped titles, broken routing, missing terminations.
---

# Survey QA

You are running a survey QA workflow. The user has (or is about to upload) two files:

1. A **Decipher XML** survey script (`.xml`) — the actual programming
2. A **questionnaire document** (`.docx` or `.pdf`) — the source of truth

Your job: compare them, identify every place the XML doesn't match the questionnaire, and produce a clear report.

## What this skill provides

A bundled Python package (`survey_qa/`) and four entry-point scripts under `scripts/`:

| Script | What it does |
|---|---|
| `parse_xml.py <xml_path>` | Parse Decipher XML → SurveyModel JSON on stdout |
| `extract_doc_text.py <doc_path>` | Extract plain text from .docx or .pdf → stdout |
| `run_checks.py <xml_path> <doc_survey_json_path>` | Run all 26 QA checks → findings JSON on stdout |
| `make_report.py <xml_path> <findings_json_path> <out_path.xlsx>` | Write color-coded Excel report |

The check engine, models, and parsers are pure-Python and live in `survey_qa/`.

## Workflow

1. **Locate both files** the user uploaded (Decipher .xml and questionnaire .docx/.pdf).

2. **Parse the XML.** Run `python scripts/parse_xml.py <xml_path>`. You'll get a SurveyModel JSON describing every question, option, term, quota, suspend, and goto in the XML. Read it.

3. **Extract the questionnaire text.** Run `python scripts/extract_doc_text.py <doc_path>`. You'll get the plain text of the document.

4. **Build a doc-side SurveyModel.** Read the extracted text. For each question you identify, produce a JSON object matching the same SurveyModel shape as the XML parser output. Write the resulting `{"survey_label": "doc", "elements": [...]}` to a temp JSON file.

   For each respondent-facing question, populate the right XmlElement variant:
   - **Radio (single-select)** → `{"tag": "radio", "label": "Q1", "title": "...", "rows": [...], "id": "doc:Q1", "position": 0, "title_raw": "..."}`
   - **Checkbox (multi-select)** → same shape with `"tag": "checkbox"` and `"atleast": 1` (or however many they need)
   - **Text** → `{"tag": "text", ...}`
   - **Select (dropdown)** → `{"tag": "select", ..., "choices": [...]}`
   - **Number / Float / HTML** → matching tag

   For each row in a radio/checkbox: `{"label": "r1", "text": "USA", "text_raw": "USA", "id": "doc:Q1:r1", "is_open": false, "is_exclusive": false}`. Use `is_exclusive: true` for "None of the above" options and `is_open: true` for "Other, specify ___" options.

5. **Run the checks.** `python scripts/run_checks.py <xml_path> <doc_survey_json_path>`. You'll get back a list of findings with severity (error / warning / info), check_id, question_label, and a human message.

6. **Present the findings to the user.** Group by severity. Errors first. Be specific — quote the XML title vs the doc title when they mismatch. Suggest fixes.

7. **Optional: write an Excel report.** If the user wants a downloadable report (or there are more than 20 findings), call `python scripts/make_report.py <xml_path> <findings_json> <output.xlsx>` and offer the file.

## Important rules

- **The questionnaire is the source of truth.** When the XML and the doc disagree, the doc wins. Phrase findings as "XML should match the questionnaire."
- **Don't over-summarize.** If there are 30 errors, list all 30 (perhaps grouped by question). Don't hide findings.
- **Routing checks fire too.** `run_checks.py` includes routing checks (RO-001–005). These flag broken `<goto>` targets, term labels not referenced in routing rules, missing `<suspend>` page breaks, etc.
- **If the XML parser fails** (malformed XML), say so and stop. Don't try to continue.
- **If your doc parsing is uncertain** for a particular question, populate `parser_meta` with `confidence < 1.0` and an `ambiguity_notes` entry. The reporter surfaces these.
- **Don't invent options.** If the questionnaire's option list is unclear, populate what you can and flag the uncertainty rather than making something up.

## Quick reference — SurveyModel shape

The skill's full JSON schema is available by running `python scripts/parse_xml.py --schema-only`. The minimum required fields per element type:

```json
{
  "survey_label": "doc",
  "elements": [
    {
      "tag": "radio",
      "label": "S1",
      "id": "doc:S1",
      "position": 0,
      "title": "Where do you live?",
      "title_raw": "Where do you live?",
      "rows": [
        {"label": "r1", "text": "USA", "text_raw": "USA", "id": "doc:S1:r1"},
        {"label": "r2", "text": "Canada", "text_raw": "Canada", "id": "doc:S1:r2"}
      ]
    }
  ]
}
```

`id`, `position`, and `title_raw` are required by the model today. Use synthetic values (e.g. `"doc:S1"`) — the checks don't depend on these matching the XML side, only on `label` matching.
