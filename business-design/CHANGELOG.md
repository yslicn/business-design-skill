# v3.3 — 2026-09-13

- Enforce 10,000–15,000 effective report body length and embedded analytical visuals with quantitative evidence.
- Bind content and Word reviews to actual reviewed artifact revisions and verify export provenance.
- Distinguish complete/partial chart bindings; reject invalid impact dependencies; support repeated images in DOCX.
- Add arithmetic/evidence checks for quantified economics and validate delivered artifacts during completion checks.
- Reuse research by input readiness, align evidence criteria, and document actual profit-pattern library coverage.
- Preserve old reports; migration is required only when preparing a new final delivery.

# Changelog

## 3.2 — 2026-09-10（Word 报告可视化与咨询版式）

- 新增 `scripts/render_report_exhibits.py`：9 类咨询展项确定性渲染（环节评分/贡献构成自动读底稿，对标条形、漏斗、优先级矩阵、路线图、贡献桥、风险矩阵、价值迁移用台账数据），观点式标题+来源行+方向性注脚，`source_refs` 悬空即拒绝渲染。
- `export_content_report.py` 升级：MD 可引用本地展项 PNG（导出校验引用数=嵌入数，不一致不发布）、封面（`--title/--subtitle/--company/--date`）、目录域、页码页脚、图注样式、斑马纹表格；封面/目录文字计入字符清单核对，保真校验不放松。
- 04 步新增 `exhibit_plan.json` 展项计划（与 MD/JSON 同步，观点式标题，数据逐字取自台账/底稿，典型 8–14 个）；MD 以 `![X01 标题](exhibits/X01.png)` 引用，图注即标题。
- 契约新增"图表与版面"章节：图表与正文不重复表达、方向性测算必须带图上注脚、unknown 不画成确定值；Architect 评审范围覆盖展项内容质量（标题观点式、数据一致、该有图而无图），像素级渲染问题除外。
- 交付边界更新：Word 内嵌展项图表属默认交付；PPT/HTML 演示类仍交独立 skill。
- 新增 `tests/test_exhibit_renderer.py`（6 项）；用真实项目数据完成 9 展项试点并页面级验收（封面/目录/图表页/页码渲染正常）。

## 3.1 — 2026-09-10（信息密度与结构化正文）

- 修复最终报告信息密度低于过程产物的问题：04 步输入加入 `research_report.md`，事实引用从"只准台账 Exx"改为"可回溯即可"（台账优先，研究报告事实引 Rxx 并在定稿前补录台账）。
- `market_insight.schema.json` 证据条目新增可选 `supporting_detail`（原文细节/研究报告定位），statement 作为索引、detail 供写报告展开；存量台账向后兼容。
- Analyst 3d 从"预测性压缩"改为完整性入账：研究报告中所有支撑判断的量化事实均须入台账，独立主体不打包成合成证据；03e 评审增加台账完整性抽样对照，台账瘦即返工。
- 报告写作流程加入章级证据池：写每章前先从台账全字段与研究报告提取相关事实清单，论据从池中取用，改变判断权重的事实不进正文须说明原因。
- 正文新增结构化章节骨架：每章必答决策问题、核心判断、带编号与数字的论据、论证、取舍与边界五要素显式完备；核心判断至少两个独立量化证据或显式数据缺口。
- 独立评审量表六维扩为七维，新增"论据充分性"（对照研究报告检查论据利用深度）；`content_quality_report.json` dimensions 同步增加 `argument_sufficiency`；Architect 第二层评审增加证据利用检查。

## 3.0 — 2026-09-10（本地内容流程）

- 默认交付顾问撰写的完整 MD 与同内容 DOCX；JSON 保留为结构化分析底稿，三者职责分离且共同核对。
- 新增内容写作/独立评审契约与下游展示交接契约，HTML、37 模块和视觉审计退出默认发布门；保留历史脚本与项目。
- 新增 export_content_report.py，使用 Pandoc + python-docx 保留长文、表格、脚注与链接，记录源 hash；转换结果不自动冒充咨询质量验收。
- project_state schema 1.3 要求 JSON/MD/DOCX/质量报告，不要求 HTML；旧版 1.2 校验保持兼容。
- insight_review schema 1.1 将固定研究字数降为诊断，保留证据、覆盖、输入就绪度硬门并要求充分性理由。
- 更新顾问和架构师指令、修正环节选择硬门的否定逻辑；本地备份完成，未发布 GitHub。

## 2.1 — 2026-08-08

- 默认核心发布升级为 `business_design.json`、自动生成的 Markdown、离线 HTML、可编辑 DOCX 四交付物；`content_quality_report.json` 升级为 schema 2.0。
- 新增共享报告模型、HTML/CSS/DOCX renderer、统一跨格式审计、重复字段 mutation gate 与 bundle 原子发布锁。
- `project_state` 升级到 schema 1.2；迁移脚本要求四种核心格式，PPT/Slide 继续作为 optional export。
- 保持 `business_design.json` schema 1.3、`slide_design_v2` 和既有测试产物不变；未发布 GitHub。

## 2.0 — 2026-08-08

- 默认核心交付切换为 `business_design.json` + 自动生成的 `business_design.md`。
- Markdown 写入 JSON source SHA-256，并新增 `audit_business_design_md.py` 与 `content_quality_report.json`。
- `project_state.schema.json` 增加 `core_status`、`core_artifacts`、`optional_exports`；新增 `migrate_project_state.py`，旧状态默认不覆盖。
- `SKILL.md` 迁移为 7 步内容优先流程和 3 个 xor 门；PPT、Slide Design、Visual consultant 降为 optional extension/export。
- 兴业 v3 已备份旧 MD、重新生成 v2 MD，内容审计 PASS，project state 迁移为 `core_status=waiting_for_user`；历史 PPT 登记为 optional export failed。

## 1.7 — 2026-08-08

- 新增 `export_coverage_inventory.py`，为 Visual consultant 生成确定性 coverage inventory。
- 新增 `content_projection.py`，统一 Business 侧可见内容投影、数字等价转换和结论强度保护；metadata-only 内容不再贡献保真覆盖。
- 加强 `visual_intent.structure` 的 comparison/matrix/process/timeline/hierarchy/bridge/parallel 关系完整性校验。
- 新增 `verify_slide_design_handoff.py`，实际调用当前 `slide_design_v2` adapter 与 PageSpec validator，检查字段和血缘是否丢失。
- 研究报告审计改为正文/参考文献分离，并增加重复段落、重复占比、唯一正文占比和密度门。
- 更新 `SKILL.md`、Visual/Report Consultant 指令和 `project_state.schema.json`，记录 coverage inventory 与下游 handoff 状态。
- 新增 28 项回归测试；Business 单元测试总数由 25 增至 53。
