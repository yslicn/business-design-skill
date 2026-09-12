---
name: business-design
description: 基于 VDBD（价值转移业务设计，参考 IBM BLM）开展企业业务设计、客户选择、价值主张和盈利模式设计。默认交付有明确观点、充分论证和证据支持的 Markdown 正文及同内容 DOCX；JSON 用于结构化分析与校验。PPT、HTML 等可视化交由独立 skill 按模板生产。
---

# Business Design

> Skill version: 3.3（内容报告优先）

## 交付边界

本 skill 负责研究、业务判断、完整论证、独立评审与长文报告。默认面向用户交付：

- `business_design.md`：顾问撰写并经独立评审的完整报告，是叙述正文的唯一母稿。
- `business_design.docx`：由同一 MD 转换的可编辑阅读版；完整保留正文、表格、来源与限定条件，并带咨询版式（封面、目录、页码）与确定性渲染的展项图表（`exhibit_plan.json` 规划、`render_report_exhibits.py` 渲染）。

`business_design.json`（沿用 schema 1.3）是内部结构化分析底稿，保存评分、候选模式、机制、证据和假设关系，供确定性校验与复用。JSON 不再作为报告全部措辞的容器；不能把 JSON 字段列表机械当成报告。MD 可以充分解释因果、比较和取舍，事实一律可回溯：优先引用证据台账 `[Exx]`，研究报告中有而台账未收录的事实可进正文（引 `[Rxx]` 并在定稿前补录台账），但不得与 JSON 出现矛盾的决策、数字、假设。业务结论变更时先同步底稿和正文，再共同评审。DOCX 不独立编辑业务内容。

PPT、HTML、网页、PDF 和展示模板不是默认交付，也不是核心完成条件；Word 报告内嵌的展项图表属于默认交付（数据图表与版式，不是页面模板）。只有用户明确需要时才交给另一个可用 skill 做演示类交付；不在本 skill 中设计页面布局或 PPT 模板。用户指定交付形式时遵循其要求。

## 工作流程

1. **明确决策问题**：记录 `input.*` 和 `requirement.json`，明确公司、诉求、业务边界、地域、期间与资源约束。只对会改变判断的缺失信息提问，其他假设明确记录。
2. **研究和证据**：按 `agents/analyst.md` 判断输入状态：新研究形成 `research_spec.json` 并开展可追溯研究；已有充分材料直接复用并核对版本；局部缺口只补证。保留 `research_report.*`、`market_insight.json`、`research_report_audit.json`。复用仍有效的已给研究。重点是价值链利润迁移、客户付费逻辑、竞争与企业胜任权，不能以篇幅或来源数量替代输入就绪度。
3. **独立输入评审**：Report consultant 按 `agents/report-consultant.md` 输出 schema 1.1 的 `insight_review.json`（字数仅诊断，记录输入充分性理由）；证据或研究缺口回研究，结构化错配只修底稿。输入通过后才能开展正式设计。
4. **设计并写完整报告**：Report consultant 以 `market_insight.json` 和 `research_report.md` 为事实来源，阅读 `reference/vdbd-method.md`、`reference/profit-models.md` 和 `reference/content-report-contract.md`，完成 JSON 分析底稿、MD 正文和 `exhibit_plan.json` 展项计划（观点式标题、数据取自台账/底稿）。先形成公司特定的结论与论证；写每章前先建章级证据池（从台账全字段与研究报告提取该章相关事实），再按结构化骨架成文：必答决策问题、核心判断、带编号、必要时含同口径数字的论据、论证、取舍与边界。正文必须满足下述字数与图文数据硬门；不以卡片数量或一页一观点组织长文。
5. **独立业务与正文评审**：VDBD Architect 按 `agents/vdbd-architect.md` 同时评审 JSON、MD 与证据，落盘 `review_notes.md`。检验观点是否值得管理层据此行动、论证是否充分、有哪些反例和失败条件，而不只看字段齐全。未通过则定向修改，再复审。
6. **生成 DOCX 并验收内容**：先渲染展项再转换正文（命令见下）；检查展项嵌入数、DOCX 内容保真和实际可读性，形成 `content_quality_report.json`，更新项目状态后执行 `python3 scripts/validate_artifacts.py --market <project>/market_insight.json --insight-review <project>/insight_review.json --business <project>/business_design.json --state <project>/project_state.json` 检查状态一致性。标题层级、正文、展项图注、比较表、目录和分页服务长文阅读；不能用拆短正文、缩字、字段索引或重复附录解决排版。
7. **交付与反馈**：给用户 MD、DOCX 链接及核心判断。`waiting_for_user` 表示质量通过、待反馈；只有用户明确验收才置 `completed`。事实问题回研究，策略与论证问题回步骤 4，DOCX 版式问题只回步骤 6。

步骤沿用项目状态的 01–07 编号，其中步骤 03 包含研究与输入评审，04 为设计，05 为业务评审，06 为交付，07 为用户验收。

独立评审使用与产出者隔离的 subagent 上下文：研究输入由独立 Report consultant 评审，设计与正文由独立 Architect 评审。传入本轮必要材料即可。宿主不支持隔离时如实标记 `independent_review=pending`，可以交草稿，但不能伪称已通过独立评审。不以重复无变化的审计消耗时间；只修复具体问题。

## 证据衔接、可靠交付与局部修订

从 deep-research 接手、证据更新、展项取数或准备交付时，按需读 [衔接与可靠性](reference/reliability-and-handoff.md)。复用原始证据和已核实的来源关系，不继承未核查的业务就绪结论。新版需保留 `evidence_map.json` 的上游 ID→本地 Exx 映射与源文件哈希；不改变已有 market_insight schema。

## 默认执行入口

从本 skill 目录执行；Python 需 `python-docx`，转换需 `pandoc`。使用宿主已有依赖；缺失则报告具体缺项，不自动安装。

```bash
python3 scripts/audit_research_report.py <project>/research_report.md \
  --advisory-length --output <project>/research_report_audit.json
python3 scripts/validate_artifacts.py \
  --market <project>/market_insight.json \
  --insight-review <project>/insight_review.json \
  --business <project>/business_design.json
python3 scripts/render_report_exhibits.py <project>/exhibit_plan.json <project>/exhibits \
  --business <project>/business_design.json --market <project>/market_insight.json
python3 scripts/export_content_report.py \
  <project>/business_design.md <project>/report-vN \
  --title "<报告标题>" --subtitle "<副题>" --company "<公司>" --date "<日期>"
```

转换器只负责生成同内容 MD、DOCX 和 `report_manifest.json`，不生成业务观点，也不自动宣称内容质量 PASS。每次使用新输出目录，避免覆盖历史交付。完成 DOCX 渲染检查后，按 `reference/content-report-contract.md` 写质量报告；正文评审者与 DOCX 审查者分别提交包含实际受审文件哈希的 `content_review_receipt.json`、`docx_review_receipt.json`，格式见可靠性参考；交付检查同时验证导出器的 `report_manifest.json`，不能仅更新质量报告哈希沿用旧评审。内容修改会使已有评审与导出失效，需要重审受影响部分并重新转换。

## 正文交付硬门

用户明确要求：正式业务设计报告有效正文 **10,000–15,000 字（含上下限）**，且正文同时有可视化和数据内容。字数不足或超限、纯文字、只有装饰图、只有概念图而无数据分析，均不得正式交付 PASS。研究输入的篇幅规则不因此改变。

按 [内容报告契约](reference/content-report-contract.md) 核验。运行 `python3 scripts/check_content_gates.py --project <project>`；最终 delivery 和完成状态检查自动执行。未通过时补分析、补证或精修，不靠重复段落、来源清单或捏造数字凑数；资料确实不足时明确交草稿。

## 内容质量标准

- 七章形成一条能解释的决策链：市场扫描 → 客户选择 → 价值主张 → 盈利模式 → 活动范围 → 战略控制 → 风险管理。
- 每章结构化完备：开篇列必答决策问题，显式给出核心判断，论据带证据编号，量化判断保留具体数字与口径，论证完成事实到判断的推理，收尾交代替代方案与成立条件。不要把五个标签机械复制成所有章节的同构模板。
- 证据充分性按判断类型确定：量化结论有可核实、同口径的量化依据；合同、客户流程、能力边界可由直接相关的定性一手材料支持。不按“两条量化证据”凑配额，不把行业数字当成客户付费意愿。关键缺口须说明是否阻断推荐或只能支持方向性判断。
- 客户选择保留六维评分、55%/45% 默认权重或合理替代权重、可复算贡献及取舍；分数是比较依据，不是客观事实。
- 盈利模式先绑定实际采用的模式库及来源；无完整库时明确筛选范围。保留候选比较、客户价值等式、价值获取机制、收费合同、单位经济性、敏感性与验证测试。增长或融资计划不能代替盈利模式。标记 quantified 的单位经济性或盈利测算须提供可复算的 `economics_ledger.json`，见 [盈利测算底稿](reference/economics-ledger.md)。
- 内容丰富意味着影响决策的信息充分；不等于重复观点、堆行业背景、扩充同义句或把所有资料塞进正文，同样不等于把研究报告的量化论据压缩成定性结论。研究与台账中会改变判断权重的事实，要么进入正文支撑论证，要么说明为何不影响结论。主文给论证，附录给评分明细、测算和来源。
- 具备比较性或多维性的内容配展项图表：观点式标题、数据可回溯、方向性测算带注脚；图表与正文不重复表达，版式由导出器统一处理。
- 事实、估算、建议、假设和未知分开；来源必须支持所引用的具体判断，unknown 不写成 0。

详细写作、人工评审量表、质量报告格式见 [内容报告契约](reference/content-report-contract.md)。

## 状态、兼容与可视化交接

新项目使用 `project_state.json` schema **1.3**；核心产物为 JSON、MD、DOCX、`content_quality_report.json`。质量未通过时用 `needs_revision` 或 `blocked`，可选导出使用 `optional_exports` 单独记录，失败不改变已通过的核心内容状态。

旧项目不自动重置或覆盖。复用已核实的研究与设计，在新目录补写并评审 MD 正文后按新流程交付；迁移状态时保留旧文件，使用新 schema 1.3，重新核实步骤 05/06，不继承旧 HTML PASS 为正文质量 PASS。`scripts/migrate_project_state.py` 仍是旧版 1.2 迁移器，不用于新流程。

需要 PPT/HTML 时，读 [下游交接契约](reference/presentation-handoff.md)，把完整 MD、分析底稿、来源与交付约束交给可用的模板生产 skill。不要提前把正文压成幻灯片短句，也不要假定某个下游 skill 一定存在。

`render_business_design_bundle.py`、旧 JSON→MD/DOCX renderer、37 模块模板、HTML 几何审计、Report editor 和 Visual consultant 均为 **legacy / optional**，只服务旧项目显式兼容需求。新流程不加载 `reference/report-rendering-contract.md` 等旧视觉契约，不运行旧 bundle，不以其门禁判断核心完成。历史资产保留，后续拆分到展示 skill 时再迁移。

本地改动不等于 GitHub 发布；不自动选择许可证、推送或声称已发布。

交付状态检查在 schema 1.3 的 waiting_for_user/completed 时会核对质量报告与实际文件哈希。资料不足可交明确标注的草稿，不得手填 PASS 绕过。使用 `python3 scripts/design_reliability.py delivery --project <project>` 单独检查。机器通过不证明专业判断或评审真实性。
