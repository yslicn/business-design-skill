# Optional presentation export

The core deliverables are `business_design.json`, `business_design.md`, and `content_quality_report.json`. Presentation output is optional and is not a core quality gate.

## Recommended route

Provide `business_design.md` to a document-design agent (for example Claude Cowork) and request a consulting-style HTML or Word report. Provide `business_design.json` as a fidelity reference when the tool can consume it.

Use this instruction:

> Turn the supplied business-design Markdown into a polished management-consulting report. Preserve the exact meaning, conclusion strength, protected numbers, units, evidence IDs, assumption IDs, conditions, and data gaps. Build visual hierarchy from semantic relationships such as comparison, progression, causality, hierarchy, choice, and risk-response. Do not invent facts, strengthen claims, or silently omit content. If space is limited, move detail to an appendix and list every omission. State that the presentation is a communication summary and that the accompanying JSON and Markdown are the canonical complete record.

## Required checks

Before delivery, compare the presentation with the core files:

1. action-oriented chapter conclusions remain unchanged;
2. all protected numbers and units are preserved;
3. evidence and assumption IDs remain visible or traceable;
4. estimates, unknowns, conditions, and data gaps are not hidden;
5. omitted details are listed explicitly;
6. no new factual or financial claims appear;
7. the presentation does not overwrite the source JSON or generated Markdown.

The included Markdown fidelity audit does not certify an optional presentation. Presentation tools need their own visual and content review.
