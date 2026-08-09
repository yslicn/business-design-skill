---
name: business-design
description: Evidence-led multi-agent business design for a specific company or segment. Produces a validated business_design.json and a deterministic, source-hashed Markdown report; presentation formats are optional downstream exports.
---

# Business Design

> Release line: 1.0 content-first

Use this skill when the user wants a researched business design, business-model redesign, value-capture design, or value-migration analysis for a specific company or clearly defined market segment.

## Completion contract

The only canonical business content is `business_design.json` (schema 1.3). Core completion requires:

- `business_design.json`: reviewed, schema-valid source of truth;
- `business_design.md`: deterministic projection of the JSON with its SHA-256 embedded;
- `content_quality_report.json`: PASS for schema, content fidelity, protected numbers, qualifiers, evidence IDs, assumption IDs, and source hash.

HTML, DOCX, PDF, PPTX, slide input, and other presentation artifacts are optional exports. They may summarize the core, but they must never change core status or become a second source of business truth.

## Multi-agent operating model

Keep the independent roles. Low-cost models benefit from role isolation and explicit review gates.

| Role | Responsibility |
|---|---|
| VDBD Architect | Clarifies the assignment; independently reviews the final business design |
| Analyst | Defines research requirements; structures the sourced market insight |
| Research agent or external research skill | Produces the 10,000–15,000-character sourced research report |
| Report Consultant | Reviews research readiness; designs the business model and value-capture architecture |

On hosts that support subagents, run each role in a separate agent context. Otherwise use separate tasks/sessions. The author of an artifact must not perform its independent review.

## Seven-step workflow

### 01 — Capture the request

Save the user's original input in the project directory. Do not infer a different company, industry, or strategic objective.

### 02 — Clarify the assignment

Run the VDBD Architect instructions in `agents/vdbd-architect.md`. Produce `requirement.json`. If `ready=false`, ask the user the generated clarifying questions and repeat this step.

### 03 — Build and approve market insight

1. Run the Analyst instructions in `agents/analyst.md` section 3a to create `research_spec.json`.
2. Use an available deep-research capability to produce `research_report.*`. If none is installed, ask the user to supply a sourced report; do not fabricate research.
3. Audit the report:

```bash
python3 scripts/audit_research_report.py \
  <project>/research_report.html \
  --output <project>/research_report_audit.json
```

The effective body must be 10,000–15,000 Chinese characters or an equivalent substantive length in another language. References, hidden text, and repeated content do not count.

4. Run Analyst section 3d to produce `market_insight.json`.
5. Run the Report Consultant's independent input review to produce `insight_review.json`.
6. If review status is `REVISE`, route exactly as specified: supplement research or restructure the insight. Do not continue to business design until status is `PASS`.

### 04 — Design the business

Run the Report Consultant instructions in `agents/report-consultant.md`. Produce only `business_design.json` conforming to `schemas/business_design.schema.json`.

The design must contain seven chapters and six mutually consistent design elements: customer selection, value proposition, profit/value-capture model, scope of activities, strategic control, and risk management, preceded by market scan.

Hard requirements include:

- segment choice uses market attractiveness and enterprise fit, not profit margin alone;
- default weights are 55% market attractiveness and 45% enterprise fit, unless a reasoned alternative is documented;
- profit model means a complete value-capture architecture, not a revenue target, premiumization slogan, cost program, or funding plan;
- facts, estimates, assumptions, recommendations, and data gaps remain distinct;
- every evidence and assumption reference resolves.

### 05 — Independent design review

Run the VDBD Architect review in a fresh context. Produce `review_notes.md`. If the conclusion is `REVISE`, return only the requested issues to step 04 and repeat the independent review.

### 06 — Validate and publish the core content

Run:

```bash
python3 scripts/validate_artifacts.py \
  --market <project>/market_insight.json \
  --insight-review <project>/insight_review.json \
  --business <project>/business_design.json

python3 scripts/render_business_design.py \
  <project>/business_design.json \
  <project>/business_design.md

python3 scripts/audit_business_design_md.py \
  --business <project>/business_design.json \
  --markdown <project>/business_design.md \
  --output <project>/content_quality_report.json
```

All three commands must PASS. Never hand-edit the generated Markdown. If the presentation needs better wording or structure, revise and re-review the JSON, then regenerate.

### 07 — User acceptance

Ask the user to approve the business viewpoints and content using JSON and Markdown. Route changes by cause:

- company, scope, or strategic objective changed → step 02;
- facts, market data, or evidence changed → step 03;
- judgment, customer choice, value proposition, or value capture changed → step 04;
- presentation only → optional export, without reopening the core design.

Set `core_status=completed` only after step 05 is PASS, the three core deliverables PASS, and the user accepts the content.

## Optional presentation exports

Read `reference/presentation-export.md` only when the user asks for a polished report. A presentation tool may create HTML, DOCX, PDF, or PPTX from `business_design.md` and, when needed, `business_design.json`.

Recommended workflow: give the generated Markdown to a capable document-design agent such as Claude Cowork, while instructing it not to strengthen, omit, or invent claims. A polished presentation is a communication layer, not a completeness proof. Keep the JSON and Markdown beside it.

## Recovery

Read `project_state.json` and resume from the first non-passed core step. Existing presentation files never prove that research, review, or core validation passed.

## Non-negotiable rules

- Preserve independent role review.
- Never invent sources, financial data, evidence IDs, or precise scores.
- Do not equate the most profitable value-chain segment with the best strategic entry point.
- Do not equate growth, premiumization, cost reduction, or financing with a profit model.
- JSON is the sole canonical content source; Markdown is generated.
- Optional exporters may summarize only with explicit disclosure and must not overwrite the core files.
- Do not include client data, source decks, or third-party training materials in redistributed copies of this skill.

## References

- `agents/analyst.md`
- `agents/report-consultant.md`
- `agents/vdbd-architect.md`
- `reference/vdbd-method.md`
- `reference/profit-models.md`
- `reference/presentation-export.md`
- `schemas/business_design.schema.json`
- `schemas/market_insight.schema.json`
- `schemas/insight_review.schema.json`
- `schemas/project_state.schema.json`
- `scripts/audit_research_report.py`
- `scripts/validate_artifacts.py`
- `scripts/render_business_design.py`
- `scripts/audit_business_design_md.py`
