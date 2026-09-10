# 下游可视化交接（可选）

仅在用户要求 PPT、HTML 或其他可视化时读取。默认不生成任何页面规划。

把已通过内容评审的 `business_design.md`、`business_design.json`、`market_insight.json`、`content_quality_report.json` 与源 SHA-256 交给用户指定或环境中可用的独立展示 skill。附上受众、用途、目标格式、模板路径/标识及用户明确的页数/品牌约束；模板未给定时由下游按其能力选择或澄清，不在业务设计流程新造模板引擎。

下游可以重组、概括、分页，但必须保留关键数字、口径、假设、风险、来源和结论强度；不能将方向性判断改成确定承诺。内容放不下时用续页或附录，并给出“源章节→展示位置”映射及有意省略项。只有发现业务内容问题才回传内容 skill 修订，不能为了版式自行改变业务决策。批量生产复用同一模板和此交接约束，展示 QA 归下游。

`optional_exports` 分别记录 format、renderer、status、artifacts 和 issues。失败仅影响相应可视化，不阻塞已通过的 MD/DOCX。可用的 `slide_input.json`、Visual consultant 与 slide handoff 脚本仅为旧项目 adapter，不强制用于所有下游，更不能代替完整母稿。

旧 HTML/37 模块报告流水线保留用于复现；`reference/report-rendering-contract.md`、`agents/report-editor.md` 及 `render_business_design_bundle.py` 仅在明确复现旧版时适用。不要将旧流水线的四交付物硬门带回 v3。
