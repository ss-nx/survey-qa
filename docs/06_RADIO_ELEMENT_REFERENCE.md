# Radio (Single Select) Element — Forsta Decipher Reference

Compiled from Forsta Surveys Knowledge Base:

- Single Select Element (UI): https://forstasurveys.zendesk.com/hc/en-us/articles/4409477095835-Single-Select-Element
- Single Select Question Attributes (XML): https://forstasurveys.zendesk.com/hc/en-us/articles/4409461359899-Single-Select-Question-Attributes
- More Options / Advanced Features: https://forstasurveys.zendesk.com/hc/en-us/articles/4409461380507-More-Options-Advanced-Features

---

## 1. Overview

The `<radio>` element is a **single select** question type. Participants may select only one answer. The element supports:

- Simple list layout (rows only)
- Grid layout (rows + columns)

**Mobile Optimized:** Yes

### Minimal example

```xml
<radio label="Q1" optional="0">
  <title>Are you...</title>
  <comment>Please select one</comment>
  <row label="r1">Male</row>
  <row label="r2">Female</row>
</radio>
```

### Grid example (rows + columns)

```xml
<radio label="Q1" unique="1" grouping="cols">
  <title>Which brand is your favorite and least favorite?</title>
  <col label="c1">Favorite</col>
  <col label="c2">Least Favorite</col>
  <row label="r1">Brand 1</row>
  <row label="r2">Brand 2</row>
  <row label="r3">Brand 3</row>
</radio>
```

---

## 2. Child Elements

| Element | Description |
| :---- | :---- |
| `<title>` | The question text shown to the participant. May contain HTML. |
| `<comment>` | Sub-title / instruction text displayed below the title. |
| `<row>` | An answer option (row). See Section 4 for row attributes. |
| `<col>` | A column option for grid-style questions. See Section 5 for col attributes. |

**Note:** Row labels use the prefix `r` by default (e.g. `r1`, `r2`). Column labels use the prefix `c` by default (e.g. `c1`, `c2`).

---

## 3. Question-Level Attributes

### 3.1 Core Attributes

| Attribute | Type | Description |
| :---- | :---- | :---- |
| `label` | string | Unique identifier for the element (e.g. `Q1`, `S3`). Required. |
| `optional` | boolean (`0`/`1`) | If `0`, response is mandatory. If `1`, response is optional. |
| `cond` | expression | Display condition. Question is shown only when this expression evaluates to true. |
| `where` | string | Controls where the element appears. Comma-separated list of: `survey`, `report`, `summary`, `none`, `execute`, `data`, `notdp`. |

### 3.2 Layout / Display Attributes

| Attribute | Type | Description |
| :---- | :---- | :---- |
| `grouping` | string | For grid questions: `auto`, `rows`, `cols`. |
| `randomize` | boolean | Randomize within a group set to randomize. |
| `shuffle` | string | Controls which dimension to shuffle: `rows`, `cols`, `choices`. |
| `rowShuffle` | string | Permutation mode for rows: `flip`, `rflip`, `rotate`, `reverse-rotate`, `rrotate`. |
| `colShuffle` | string | Permutation mode for columns. Same values as `rowShuffle`. |
| `shuffleBy` | string | Randomize in the same order as a previous question. Value is that question's label. |

### 3.3 Validation / Logic Attributes

| Attribute | Type | Description |
| :---- | :---- | :---- |
| `unique` | boolean/string | Prevents duplicate responses in grid questions. |
| `verify` | string | Validation function(s) applied to responses. |
| `validateRow` | expression | Per-row validation with a custom error message. |
| `validateCol` | expression | Per-column validation with a custom error message. |
| `validateCell` | expression | Per-cell validation with a custom error message. |
| `exactly` | integer | Exactly how many values must be selected. |

### 3.4 Reporting Attributes

| Attribute | Type | Description |
| :---- | :---- | :---- |
| `adim` | string | Primary report dimension: `auto`, `rows`, `cols`, `choices`. |
| `averages` | string | Controls which averages are calculated. |
| `altLabel` | string | Alternative label shown everywhere except the survey. |
| `alt` | string | Alternative text that only appears in the report. |
| `sortRows` | string | How rows are sorted: `asc`, `desc`, `survey`, `report`, `none`. |
| `sortCols` | string | How columns are sorted. Same values as `sortRows`. |
| `percentages` | boolean | If set, displays percentages. |

### 3.5 Other Attributes

| Attribute | Type | Description |
| :---- | :---- | :---- |
| `pii` | integer (0–9999) | PII protection level. Only applies to textual data. |
| `sst` | boolean | If unchecked, excludes element from simulated testing data. |
| `looprows` | string | Comma-separated label suffixes for loop elements. |
| `source` | string | HTML file from which data is read. |

---

## 4. Row (`<row>`) Attributes

| Attribute | Type | Description |
| :---- | :---- | :---- |
| `label` | string | Internal identifier, e.g. `r1`, `r2`. |
| `value` | string/integer | Data value stored in results. |
| `open` | boolean (`"1"`) | Triggers an open-end text box for this row. |
| `exclusive` | boolean (`"1"`) | Deselects all other rows when chosen. |
| `terminate` | boolean (`"1"`) | Terminates the respondent when this row is selected. |
| `rowstyle` | string | Visual style override. `"hidden"` hides the row. |
| `aggregate` | boolean | Excludes this row from average/std dev calculations. |
| `cond` | expression | Display condition for this specific row. |
| `randomize` | boolean | Participates in randomization. |
| `optional` | boolean | Overrides mandatory at the row level. |
| `alt` | string | Alternative text shown only in the report. |
| `altLabel` | string | Alternative label for recoding/relabeling. |
| `okUnique` | boolean | Allows this row to be selected twice when uniqueness is required. |

---

## 5. Column (`<col>`) Attributes

| Attribute | Type | Description |
| :---- | :---- | :---- |
| `label` | string | Internal identifier, e.g. `c1`, `c2`. |
| `value` | string/integer | Data value stored in results. |
| `cond` | expression | Display condition for this specific column. |
| `randomize` | boolean | Participates in column randomization. |
| `optional` | boolean | Makes this column optional if question is set to mandatory. |
| `hidden` | boolean | Hides the column from participants. |
| `alt` | string | Alternative text shown only in the report. |
| `altLabel` | string | Alternative label for recoding/relabeling. |

---

## 6. Condition Syntax (cond=)

| Expression | Meaning |
| :---- | :---- |
| `ans(Q1,[r1])` | Q1 was answered with row r1 |
| `ans(Q1,[1])` | Q1 value equals 1 |
| `Q1.r1` | Row r1 was selected in Q1 |
| `not ans(Q1,[r99])` | Q1 was NOT answered with r99 |
| `Q1.r1 or Q1.r2` | Either r1 or r2 selected in Q1 |
| `label("condName")` | References a named `<condition>` element |

---

## 7. Notes for QA Tool

### What to parse from `<radio>`

- `label` — question identifier (required)
- `optional` — maps to `is_required` (optional="0" → required)
- `cond` — display condition
- `where` — skip questions with `where="execute"` when comparing to doc
- `grouping` — note if grid-style
- `unique` — store, low QA priority
- `<title>` text — strip HTML tags
- `<comment>` text — store separately
- All `<row>` children — parse label, value, open, exclusive, terminate, rowstyle, aggregate
- All `<col>` children — parse label, value (grid questions)

### Gaps identified vs current 04_DECIPHER_XML_REFERENCE.md

| Gap | Detail |
| :---- | :---- |
| `<comment>` element not documented | Sub-title text under question title |
| `<col>` elements not documented | Grid-style radio has columns |
| `where=` valid values incomplete | Missing: `summary`, `none`, `data`, `notdp` |
| `aggregate` on `<row>` not documented | Excludes row from stats calculations |
| `okUnique` on `<row>` not documented | Row-level uniqueness override |

### Canonical model gaps (items to add)

| Field | Where | Reason |
| :---- | :---- | :---- |
| `comment` | `Question` | Sub-title / instruction text |
| `cols` | `Question` | List of `Option` objects for column dimension |
| `grouping` | `Question` | `auto`/`rows`/`cols` for grid layout |
| `unique` | `Question` | Uniqueness constraint |
| `aggregate` | `Option` | Exclude from stats |
| `is_open_optional` | `Option` | Distinguish mandatory vs optional open-end |
