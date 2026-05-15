# Survey QA Tool — Decipher XML Reference

## Overview

Forsta Decipher XML is the survey scripting format used to define all questions, logic, routing, and quotas. This document captures the conventions relevant to the QA tool's XML parser.

---

## Document Structure

```xml
<survey>
  <samplesources>...</samplesources>   <!-- Panel/source config -->
  <condition label="..." cond="..."/>  <!-- Named reusable conditions -->
  <quota label="..." sheet="..."/>     <!-- Quota definitions -->
  
  <!-- Questions appear here, in order -->
  <radio label="S1" ...>
    <title>Question text</title>
    <row label="r1" value="1">Option text</row>
    <row label="r2" value="2">Option text</row>
  </radio>

  <suspend/>  <!-- Page break -->

  <checkbox label="S3" ...>
    ...
  </checkbox>
</survey>
```

---

## Question Types

### `<radio>` — Single select

```xml
<radio label="S1" cond="..." where="survey">
  <title>Which of the following best describes...</title>
  <row label="r1" value="1">Option A</row>
  <row label="r2" value="2">Option B</row>
  <row label="r99" value="99" exclusive="1">None of the above</row>
</radio>
```

Key attributes: `label`, `cond`, `where`, `randomize`, `values`

---

### `<checkbox>` — Multi-select

```xml
<checkbox label="S3" atleast="1" cond="...">
  <title>Select all that apply...</title>
  <row label="r1" value="1">Option A</row>
  <row label="r2" value="2" open="1">Other (specify)</row>
  <row label="r99" value="99" exclusive="1">None of the above</row>
</checkbox>
```

Key attributes: `label`, `cond`, `atleast`, `atmost`

---

### `<text>` — Open-end text

```xml
<text label="S5" optional="0">
  <title>Please describe...</title>
</text>
```

Key attributes: `label`, `optional`, `size`, `cond`

---

### `<number>` — Numeric input

```xml
<number label="S8" size="4" cond="...">
  <title>How many years have you...</title>
</number>
```

Key attributes: `label`, `size`, `min`, `max`, `cond`

---

### `<select>` — Dropdown

```xml
<select label="S10" cond="...">
  <title>Please select your region</title>
  <row label="r1" value="1">North</row>
  <row label="r2" value="2">South</row>
</select>
```

---

### `<float>` — Decimal input

```xml
<float label="S9" cond="...">
  <title>Enter a percentage...</title>
</float>
```

---

## Row (`<row>`) Attributes

| Attribute | Values | Meaning |
|---|---|---|
| `label` | `r1`, `r2`... | Internal identifier |
| `value` | `"1"`, `"2"`... | Data value stored in results |
| `open` | `"1"` | Triggers an open-end text box |
| `exclusive` | `"1"` | Deselects all others when chosen |
| `terminate` | `"1"` | Terminates the respondent |
| `rowstyle` | `"hidden"` | Hidden from respondent (internal use) |

---

## Display Conditions (`cond=`)

The `cond=` attribute controls whether a question is shown. It uses Decipher expression syntax.

### Common patterns

| Expression | Meaning |
|---|---|
| `ans(S1,[r1])` | S1 was answered with row r1 |
| `ans(S1,[1])` | S1 value equals 1 |
| `S3.r2` | S3 row r2 was selected |
| `not ans(S1,[r99])` | S1 was NOT answered with r99 |
| `S1.r1 or S1.r2` | Either r1 or r2 selected in S1 |
| `S1.r1 and S2.r3` | Both conditions true |
| `flt(S8) >= 18` | Numeric value of S8 >= 18 |
| `label("condName")` | References a named `<condition>` |

### Named conditions

```xml
<condition label="qualifies" cond="ans(S1,[r1]) and ans(S3,[r2,r3])"/>
```

Referenced elsewhere as `label("qualifies")`.

---

## Routing Elements

### `<suspend/>`
Page break — splits questions across survey pages. No attributes needed.

### `<goto>`
Unconditional or conditional jump:
```xml
<goto cond="ans(S1,[r99])" target="end"/>
```

### `<block>`
Wraps a group of questions shown conditionally:
```xml
<block cond="ans(S2,[r1])">
  <radio label="S3" ...>...</radio>
  <text label="S4" ...>...</text>
</block>
```

---

## Quota Elements

```xml
<quota label="quota_age" sheet="Age Quotas" overquota="term_overquota">
  <condition label="18_34" cond="flt(Age) >= 18 and flt(Age) <= 34"/>
  <condition label="35_54" cond="flt(Age) >= 35 and flt(Age) <= 54"/>
</quota>
```

Key attributes: `label`, `sheet`, `overquota` (target label on full)

---

## Terminate Logic

Respondents can be terminated by:
1. `terminate="1"` on a `<row>` — triggers on selection
2. `<goto target="terminate_label">` — conditional jump to a terminate block
3. Quota `overquota=` pointing to a terminate element

---

## `where=` Attribute

Controls where a question appears in the Decipher system:

| Value | Meaning |
|---|---|
| `survey` | Shown to respondent only |
| `report` | In reporting only, not shown live |
| `execute` | Runs logic but not displayed |
| `execute,survey,report` | All three |

Questions with `where="execute"` are internal/logic-only and should not be compared against doc questions.

---

## HTML in Titles

Question titles often contain HTML:
```xml
<title><b>Which</b> of the following do you use?<br/></title>
```

The XML parser should strip HTML tags when extracting title text for comparison.

---

## Pipes / Carry-forward (Future Phase)

Decipher supports piping previous answers into question text:
```xml
<title>You selected ${S3}. Why did you choose this?</title>
```

And carry-forward rows from previous questions. This is out of scope for Phase 1–2 but should be noted as a known complexity.
