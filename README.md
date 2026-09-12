# Business Design Skill

Current release: **v3.3**.

Final reports must contain **10,000–15,000 effective body characters/words**, analytical visuals, and evidence-linked quantitative content. Chinese characters count individually; Latin/alphanumeric words count as tokens. Headings, references, appendices, captions and exact repeated body blocks are excluded. These are delivery gates, not a guarantee of reasoning quality.

Version 3.3 also includes reviewer-authored revision receipts, MD/DOCX export provenance, partial chart-binding disclosure, validated update dependencies, and arithmetic checks for quantified economics. See `business-design/reference/reliability-and-handoff.md` and `business-design/reference/economics-ledger.md`.

An evidence-led, multi-agent business-design workflow that simulates a small strategy-consulting team while remaining usable with lower-cost language models.

The skill's core value is the business viewpoint and supporting content, not a specific slide or document renderer. Since v3 the default deliverables are a consultant-written long-form report with embedded consulting-style exhibits:

- `business_design.md` — the reviewed narrative manuscript and single source of truth for the report text;
- `business_design.docx` — same-content editable Word report with a consulting layout: cover page, table of contents, page numbers, captions, and deterministically rendered exhibit charts (bar benchmarks, scoring, funnels, priority matrices, roadmaps, contribution bridges, risk maps, value-migration flows);
- `business_design.json` — canonical structured analysis draft (scoring, profit-model candidates, mechanisms, evidence, assumptions) for deterministic validation and reuse;
- `exhibit_plan.json` + `exhibits/` — exhibit plan synced with the manuscript; PNGs are rendered by `render_report_exhibits.py` with every number traceable to the evidence ledger;
- `content_quality_report.json` — content review and delivery audit.

Every layer enforces traceability: facts cite evidence-ledger entries `[Exx]` (with `supporting_detail` preserved from the research report), assumptions are numbered `[Axx]`, estimates are labeled, and unknowns are never written as zero.

HTML, PDF, and PowerPoint remain optional downstream presentation formats handled by other skills. For a polished interactive report, pass the full Markdown plus the analysis draft to a capable presentation skill (see `business-design/reference/presentation-handoff.md`).

**Important output boundary:** this skill generates and validates the business-design content in JSON and Markdown. It does **not** generate the showcased HTML reports. The example HTML reports are separate presentation artifacts created by Claude Cowork from the Markdown produced by this skill. They demonstrate one possible downstream presentation workflow, not a built-in HTML renderer or a guaranteed Claude Cowork output.

## Install

Copy the `business-design` directory into the skills directory used by your agent:

```text
Claude Code: ~/.claude/skills/business-design
Codex:       ~/.codex/skills/business-design
OpenCode:    ~/.config/opencode/skills/business-design
```

OpenCode paths can vary by installation; use the directory documented by your host. The workflow is plain Markdown, JSON Schema, and Python, so other agents can use it by loading `business-design/SKILL.md`.

Install the Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Word export additionally requires `pandoc` on the host; exhibit rendering requires `matplotlib` (in `requirements.txt`). Chinese rendering defaults to PingFang SC on macOS and Noto Sans CJK elsewhere.

## Use

Ask your agent to use the `business-design` skill and provide:

- the company or precise company profile;
- industry and geography;
- current business and revenue sources;
- strategic objective or core pain point;
- constraints and any existing research.

The workflow keeps Analyst, Report Consultant, and VDBD Architect reviews independent. Hosts without subagents can use separate sessions.

## Research dependency

The skill can call any installed deep-research capability. It does not bundle or require a specific proprietary research tool. If no research capability is available, supply a sourced research report; the skill must not fabricate one.

## Presentation

The Word report with embedded exhibits is the default readable deliverable. For slides, HTML, or PDF decks, see `business-design/reference/presentation-handoff.md`; optional presentation tools are not included and are not required to complete the business design. Do not compress the manuscript into slide bullets before handing off.

The published examples use this production chain:

```text
Business Design skill -> business_design.json + business_design.md + business_design.docx
Claude Cowork         -> presentation-style HTML based on business_design.md
```

The JSON, Markdown, and DOCX remain the canonical outputs. The HTML is a non-canonical communication layer and may reorganize or summarize content for readability.

## Examples

[![查看中文样例报告](https://img.shields.io/badge/📄-中文报告-173F5F?style=for-the-badge)](https://yslicn.github.io/business-design-skill/report-cn.html)
[![View English Sample Report](https://img.shields.io/badge/📄-English_Report-3478A7?style=for-the-badge)](https://yslicn.github.io/business-design-skill/report.html)

Both are presentation-only, pseudonymized public-information case studies. Their underlying JSON and Markdown were generated by this skill; Claude Cowork subsequently created the HTML reports from the Markdown. See the [example disclosures](examples/README.md).

## Privacy

Never commit client workspaces, original input decks, research caches, or generated reports containing confidential information. Public examples must be anonymized and separately reviewed.

## Method and third-party rights

This repository contains an original workflow and original explanatory text. It does not include source training decks, third-party diagrams, or a copied proprietary profit-model catalogue. See `THIRD_PARTY_NOTICES.md`.

## License

Licensed under the [Apache License 2.0](LICENSE).

---

## 中文说明

这是一个以证据、独立评审和多 Agent 协作为核心的业务设计 skill。自 v3 起默认交付：顾问撰写的完整报告正文（`business_design.md`）、同内容咨询版式 Word 报告（封面/目录/页码/确定性渲染的展项图表）、结构化分析底稿 `business_design.json` 与内容质量报告。事实一律可回溯（证据台账 `[Exx]`、假设 `[Axx]`、估算显式标注、未知不写成 0）。HTML、PDF、PPT 仍是可选下游呈现层，交独立展示 skill 处理。

**样例生成边界：**样例中的 `business_design.json` 和 `business_design.md` 由本 skill 生成并校验；HTML 咨询报告是在此之后，由 Claude Cowork 基于该 Markdown 另行制作。本 skill 不内置或承诺生成样例中的 HTML 效果，HTML 仅代表一种可选的下游呈现方式。

仓库提供可直接在线浏览的[中文样例](https://yslicn.github.io/business-design-skill/report-cn.html)和[英文样例](https://yslicn.github.io/business-design-skill/report.html)。两个样例均为基于公开信息的化名案例，只分发 HTML 演示报告，不分发底层 JSON、Markdown 或研究工作区。

安装时将 `business-design` 目录复制到 Claude Code、Codex、OpenCode 或其他 Agent 的 skill 目录。若没有 subagent，可用多个独立会话分别承担 Analyst、Report Consultant 与 VDBD Architect。
