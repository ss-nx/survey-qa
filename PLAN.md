# Survey QA Tool — Plan

The canonical project plan, architecture, and coding conventions live in [`docs/`](docs/). This file is a pointer.

## Design docs

| File | Purpose |
|---|---|
| [`01_PROJECT_OVERVIEW.md`](docs/01_PROJECT_OVERVIEW.md) | What this is, problem, constraints, tech stack |
| [`02_ARCHITECTURE.md`](docs/02_ARCHITECTURE.md) | Architecture diagram, design decisions, canonical model |
| [`03_BUILD_PLAN.md`](docs/03_BUILD_PLAN.md) | Phased delivery plan with deliverables per phase |
| [`04_DECIPHER_XML_REFERENCE.md`](docs/04_DECIPHER_XML_REFERENCE.md) | Decipher XML element reference |
| [`05_CODING_CONVENTIONS.md`](docs/05_CODING_CONVENTIONS.md) | How to add checks, models, question types; PR workflow |
| [`06_RADIO_ELEMENT_REFERENCE.md`](docs/06_RADIO_ELEMENT_REFERENCE.md) | Full radio element attributes |
| `07_DECIPHER_FUNCTION_LIBRARY.md` | Decipher function library — used by doc parser for `cond` translation |

## Current phase status

- **Phase 1** — XML parser + core checks ✅ DONE
- **Phase 2** — Doc parser + caching ✅ DONE
- **Phase 3** — Checkbox / Text / Select / Routing checks ✅ DONE
- **Phase 4** — Display condition comparison (cond AST diff) — in planning
- **Phase 5** — MCP server (interactive use inside Claude) — in planning
- **Phase 6** — GitHub check management workflow (branch + PR per check change) — in planning
- **Phase 7** — Streamlit UI — backlog

## Active architectural refactor

Currently in progress: collapsing the two-model design (`SurveyModel` from XML + `QuestionnaireModel` from doc) into a **single unified model**. Both parsers will produce the same `XmlRadio` / `XmlCheckbox` / `XmlText` / etc. types. Parser-side annotations (confidence, source excerpt, raw English logic) move to an optional `_meta: ParserMeta` field that checks ignore and reporters surface.

See [`docs/02_ARCHITECTURE.md`](docs/02_ARCHITECTURE.md) and [`docs/05_CODING_CONVENTIONS.md`](docs/05_CODING_CONVENTIONS.md) for the target design.
