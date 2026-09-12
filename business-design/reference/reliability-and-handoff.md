# 3.2 证据衔接与可靠性

## 上游证据

优先读取 deep-research 的 research_data.json、report.md、bindings.json、review_report.json。独立检查其实际复核范围、文件版本和重要未关闭问题，不能直接将上游 PASS 当业务输入充分。

```bash
python3 scripts/design_reliability.py evidence --data <research>/research_data.json > <project>/upstream_evidence.json
```

只读导入裸列表或 items 包装，完整保留上游对象和 ID、原文件哈希。导入仅保存事实材料，不推导 verified、不自动生成市场吸引力或客户建议。缺少 kind/locator 记录为缺口，不猜测补齐。
Analyst 生成市场台账时保留稳定 Exx/Sxx，另写 evidence_map.json：

```json
{"upstream_sha256":"实际源哈希","mappings":[{"upstream_id":"D001","local_evidence_id":"E01","source_ids":["S01"]}]}
```

映射必须逐项存在、语义相同，合并/拆分记录原因；同一来源的多个数据点不算独立来源。该映射由 Analyst 建立、输入 Reviewer 核实，当前工具不自动把两套 schema 合并。运行 `python3 scripts/design_reliability.py mapping --data <research>/research_data.json --market <project>/market_insight.json --map <project>/evidence_map.json` 核对 ID、来源关系和上游哈希；输出未映射项供决定是否需要补充，不把部分映射称为全量覆盖。该检查不能证明语义等价。研究报告独有事实补回证据包，不用重新搜索已有可靠原文。

## 展项绑定

自动评分图从底稿取数，权重图例从 selection_method 读取。其他 renderer 可用 data_bindings 指向业务底稿或市场 JSON：

```json
{"id":"X01","type":"bar_ranking","action_title":"示例结论","source_refs":["E01"],"data":{"unit":"万元"},"data_bindings":{"labels":{"source":"market","pointer":"/某个实际存在的标签数组"},"values":{"source":"market","pointer":"/某个实际存在的数值数组"}}}
```

pointer 使用实际 JSON Pointer，支持 ~0/~1 转义。只绑定 renderer data 的顶层字段；不解析文字中的数字。若台账只保留文字而无可用数组，可用明确记录 input_refs、公式、单位的中间测算，独立评审核实后作为 inline 数据。不能假造字段来让 pointer 存在。
inline 与绑定同时存在必须完全一致；缺路径报错。manifest 标明 source_bound、partially_bound 或 manual_review_required，并列出 unbound_fields（含单位与轴定义等口径字段）；source_bound 只证明复制路径，不证明口径正确。未绑定的数值仍必须人工比对来源，不能将“来源 ID 存在”称为数值核实。

## 局部更新

为 MD 关键段落/摘要/图表/推荐维护 design_bindings.json：

```json
{"targets":[{"id":"summary-1","evidence_ids":["E01"],"business_pointers":["/chapters/customer_selection"]}]}
```

ID 对应正文锚点或 exhibit ID。目标 ID、证据 ID 必须有效且无重复，business_pointers 必须能解析到本轮传入的底稿。数组重排后重新生成路径并检查其业务对象 ID；无效依赖报错，不能判为可沿用。Manager 检查全部关键目标已覆盖；工具不能识别未登记的语义依赖。

```bash
python3 scripts/design_reliability.py impact --before <old>/market_insight.json --after <new>/market_insight.json --business <old>/business_design.json --bindings <old>/design_bindings.json
```

比较证据和来源变化，定位含 evidence_ids 的底稿对象及相关目标。review 定点处理；keep_candidate 仅表示未发现已声明依赖变化，不是质量 PASS。更新假设/用户约束/业务选择时也须由 Consultant 主动扩展影响面，因为这些变化不一定来自市场台账。每轮都核对摘要和最终建议是否有间接影响，保留旧文件另存新版。

## 交付文件核验

```bash
python3 scripts/design_reliability.py delivery --project <project>
```

使用现有 content_quality_report.json，无需另一套质量报告。必需 source_hashes：business_design.md、business_design.json、business_design.docx、market_insight.json、review_notes.md、docx_review_record；导出 DOCX 不在项目根目录时添加 artifact_paths，如 {"business_design.docx":"report-v2/business_design.docx"}。docx_review_artifact 指向实际渲染审查记录，review_artifact 为 review_notes.md。
存在 exhibit_plan.json 时增加其哈希与 exhibits/exhibits_manifest.json 哈希；manifest 内每张 PNG 的哈希也须正确，并核对计划以及 business/market 对象摘要是否对应本轮数据。source_hashes 只更新而图表未重渲染仍会失败。图文或证据变化后重新评审对应影响面、重渲染和导出，再更新质量报告。
对外 waiting_for_user/completed 必须通过实际文件核验；旧报告只阅读无需补齐，旧项目再发布时在新版本补凭证。PASS 标志、文件哈希不能证明评审真的独立、正文与 JSON 语义相同或 DOCX 美观，仍需核对真实 Reviewer 输出和渲染结果。


### Reviewer 的版本凭证

正文评审者在完成本轮实际审阅后写 `content_review_receipt.json`，字段如下。哈希必须来自评审时读取的文件；修改受审文件后由原评审者复核受影响部分并更新凭证，编排者不得代填 PASS 或替换旧凭证哈希。

```json
{"status":"PASS","reviewer":"实际评审任务/调用标识","reviewed_hashes":{"business_design.md":"实际摘要","business_design.json":"实际摘要","market_insight.json":"实际摘要","review_notes.md":"实际摘要"}}
```

若存在 `economics_ledger.json`，正文评审凭证也须包含它的摘要。DOCX 实际渲染审查后，由审查者写 `docx_review_receipt.json`，同样使用 status、reviewer、reviewed_hashes；哈希键为 business_design.md、business_design.docx、docx_review_record（实际审查记录的文件摘要）。凭证记录版本关系，不是身份认证，也不能替代真实评审。

交付核验读取 DOCX 同目录的 `report_manifest.json`，核对当前 MD/DOCX 摘要及导出图片。自定义转换流程也要保留同结构导出凭证。缺失或过期时交明确草稿；不得凭当前文件反向伪造转换历史。旧项目只读不要求迁移。
