# 可复算的盈利底稿

当 unit_economics 或 profitability_estimate.status 为 quantified，提供 economics_ledger.json。directional/not_available 不强求虚构数字，说明缺口与验证计划。底稿支持四则运算，不执行公式字符串；复杂模型可以分解成中间计算，不能表达的计算保留外部测算并明确尚未通过本检查，不伪填 quantified。

输入逐项记录 value、unit、evidence_ids 或 assumption_ids。使用原始精度计算，正文另行四舍五入。场景注明期间、币种和业务单位（basis）、现金转换逻辑（cash_conversion）及决策影响（decision_implication）。定量交付至少提供基准与一个有业务意义的压力/敏感性场景，不能只复制同一组输入。

以下仅为结构示例，E01、A01 必须替换为当前台账/底稿存在的编号。示例只展示一个场景，不满足完整定量交付的情景要求。

```json
{
  "covers": ["/chapters/profit_model/unit_economics"],
  "scenarios": [{
    "id": "base",
    "basis": "人民币元；每月；设备台数",
    "cash_conversion": "注明收款、付款、库存或预付周期及测算依据",
    "decision_implication": "说明何时继续投入或停止",
    "inputs": [
      {"id":"price","value":100,"unit":"元/台","evidence_ids":["E01"]},
      {"id":"volume","value":20,"unit":"台/月","assumption_ids":["A01"]},
      {"id":"variable_cost","value":60,"unit":"元/台","assumption_ids":["A01"]}
    ],
    "calculations": [
      {"id":"revenue","operation":"multiply","operands":["price","volume"],"result":2000,"unit":"元/月"},
      {"id":"unit_contribution","operation":"subtract","operands":["price","variable_cost"],"result":40,"unit":"元/台"},
      {"id":"contribution","operation":"multiply","operands":["unit_contribution","volume"],"result":800,"unit":"元/月"}
    ],
    "outputs":{"revenue":"revenue","contribution":"contribution"}
  }]
}
```

calculations 按依赖顺序排列，每项两个已存在的 operands，operation 为 add/subtract/multiply/divide。盈亏平衡、回收期或现金测算采用同样结构增加计算及 outputs 字段；分母为零时记录不成立的条件，不制造结果。

```bash
python3 scripts/check_economics.py --ledger <project>/economics_ledger.json --business <project>/business_design.json --market <project>/market_insight.json
```

机器核验编号、有限数值、四则运算与已声明覆盖路径；不能证明单位相容、输入真实、成本完整或客户愿意付费。Reviewer 必须检查收入与贡献利润输出是否符合定义，固定成本、税费、资金占用是否影响结论，以及盈利估算是否真正覆盖盈亏平衡/回收逻辑。将审阅的底稿哈希写入正文评审凭证。
