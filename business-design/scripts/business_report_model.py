#!/usr/bin/env python3
"""Deterministic consulting-semantic projection of ``business_design.json``.

The model is deliberately content-preserving: semantic roles only control
presentation and never change, summarize, or invent business values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

try:
    from .content_projection import METADATA_KEYS
except ImportError:  # script/importlib compatibility
    from content_projection import METADATA_KEYS


CHAPTER_NAMES = {
    "market_scan": "1 市场扫描",
    "customer_selection": "2 客户选择",
    "value_proposition": "3 价值主张",
    "profit_model": "4 盈利模式 / 价值获取",
    "scope_of_activities": "5 活动范围",
    "strategic_control": "6 战略控制",
    "risk_management": "7 风险管理",
}

# Labels are presentation metadata, never a second content source.
FIELD_NAMES = {
    "company": "公司", "industry": "行业", "strategic_intent": "战略诉求",
    "core_pain": "核心痛点", "story_line": "核心判断", "key_message": "核心观点",
    "five_looks": "五看分析", "look_industry_trend": "行业趋势", "look_market_customer": "市场与客户",
    "look_competition": "竞争格局", "look_self": "自身能力", "look_opportunity": "机会窗口",
    "policy": "政策窗口", "competitor_overview": "竞争格局", "current_position_assessment": "当前定位评估",
    "selection_method": "选择方法", "score_scale": "评分尺度", "scores": "六维评分",
    "market_attractiveness_weight": "市场吸引力权重", "enterprise_fit_weight": "企业胜任权权重",
    "dimension_weights": "六维权重", "formula": "加权公式", "weighting_rationale": "权重理由",
    "segment_evaluation": "环节评估", "recommended_segment": "推荐环节", "customer_segmentation": "客户细分",
    "high_value_targets": "高价值目标客户", "customer_needs_pains": "客户诉求与痛点",
    "competitor_approaches": "竞争对手方案", "differentiated_offering": "差异化价值主张",
    "statement": "主张", "rationale": "理由", "pattern_screening": "利润模式库筛选",
    "library_version": "模式库版本", "screening_scope": "筛选范围", "screening_criteria": "筛选标准",
    "screening_summary": "筛选结论", "shortlisted_model_ids": "候选模式 IDs", "candidate_models": "候选模式",
    "selected_architecture": "主辅模式架构", "architecture_statement": "架构结论",
    "selection_rationale": "选择理由", "primary_model_id": "主模式 ID", "supporting_model_ids": "辅助模式 IDs",
    "customer_value_equations": "客户价值等式", "target_customer": "目标客户",
    "incremental_revenue": "新增收益", "avoided_loss": "避免损失", "working_capital_improvement": "营运资金改善",
    "risk_reduction": "风险下降", "adoption_cost": "采用成本", "net_value_logic": "净价值逻辑",
    "value_metric": "价值指标", "value_capture_mechanisms": "价值获取机制", "offer": "提供物",
    "value_created": "客户价值", "payer": "付费方", "charging_unit": "收费单位", "price_formula": "价格公式",
    "pricing_mechanism": "定价机制", "contract_and_risk_sharing": "合同与风险分担", "revenue_timing": "收入时点",
    "margin_logic": "利润形成逻辑", "control_point": "控制点", "unit_economics": "单位经济性",
    "status": "状态", "unit": "验证单位", "revenue_formula": "收入公式", "variable_costs": "变动成本",
    "contribution_margin_logic": "贡献利润逻辑", "working_capital_and_cash_conversion": "营运资金与现金转换",
    "sensitivity": "敏感性", "profitability_estimate": "盈利测算", "summary": "摘要",
    "profit_drivers": "利润驱动因素", "break_even_or_payback": "盈亏平衡/回收期",
    "growth_and_funding_plan": "增长与融资计划（非盈利模式）", "validation_tests": "验证测试",
    "hypothesis": "验证假设", "metric": "关键指标", "threshold_or_signal": "阈值或信号",
    "validation_method": "验证方法", "cadence": "复核频率", "in_scope": "建议进入", "out_of_scope": "明确不进入",
    "business": "业务", "action": "控制动作", "control_points": "战略控制点", "point": "控制点",
    "risks": "风险与应对", "dimension": "风险维度", "risk": "风险描述", "mitigation": "缓释动作",
    "impact": "影响", "missing": "数据缺口", "recommended_action": "建议动作", "chapter": "影响章节",
    "assumptions": "关键假设", "description": "说明", "assumption_ids": "假设 IDs", "evidence_ids": "证据 IDs",
    "id": "编号", "name": "名称", "segment": "环节", "target": "目标", "decision": "决策",
    "conclusion": "结论", "overall_assessment": "总体评估", "score_rationale": "评分理由",
    "fit": "适配度", "fit_rationale": "适配理由", "mechanism": "机制", "pattern_name": "模式名称",
    "competitor": "竞争对手", "offering": "提供方案", "recent_moves": "近期动作", "current_position": "当前位置",
    "minimum": "最低值", "maximum": "最高值", "higher_is_better": "越高越好", "linked_model_ids": "关联模式 IDs",
    "linked_value_equation_ids": "关联价值等式 IDs", "profit_model": "盈利模式", "market_scan": "市场扫描",
    "customer_selection": "客户选择", "value_proposition": "价值主张", "scope_of_activities": "活动范围",
    "strategic_control": "战略控制", "risk_management": "风险管理", "data_gaps": "数据缺口",
}

SEMANTIC_KINDS = {
    "chapter_thesis", "executive_thesis", "decision", "evidence", "implication", "recommendation", "metric",
    "comparison", "score_matrix", "process", "value_chain", "value_equation", "profit_architecture",
    "value_capture", "scope_boundary", "control_mechanism", "risk_register", "assumption", "data_gap",
    "record_cards", "compact_table", "source_index", "fallback_group", "summary_context", "design_conclusions",
    "record",
}


def label(key: str) -> str:
    if key in FIELD_NAMES:
        return FIELD_NAMES[key]
    # Unknown fields remain readable and never leak a raw snake_case label.
    return "字段：" + key.replace("_", " ").strip().capitalize()


def scalar(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def pointer(parent: str, key: str | int) -> str:
    part = str(key).replace("~", "~0").replace("/", "~1")
    return f"{parent}/{part}" if parent else f"/{part}"


@dataclass(frozen=True)
class ReportBlock:
    kind: str
    title: str
    source_pointer: str
    role: str = "supporting"
    relation: str = "parallel"
    priority: int = 2
    value: Any = None
    children: tuple["ReportBlock", ...] = field(default_factory=tuple)
    columns: tuple[str, ...] = field(default_factory=tuple)
    rows: tuple[tuple[Any, ...], ...] = field(default_factory=tuple)
    row_pointers: tuple[str, ...] = field(default_factory=tuple)
    source_pointers: tuple[str, ...] = field(default_factory=tuple)
    presentation_hint: str = ""


@dataclass(frozen=True)
class ReportSection:
    key: str
    title: str
    source_pointer: str
    blocks: tuple[ReportBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReportDocument:
    source_name: str
    source_sha256: str
    company: str
    sections: tuple[ReportSection, ...]
    evidence_ids: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    visible_atoms: tuple[tuple[str, str], ...]

    def iter_blocks(self) -> Iterable[ReportBlock]:
        for section in self.sections:
            yield from _iter_blocks(section.blocks)

    def blocks_by_kind(self, kind: str) -> tuple[ReportBlock, ...]:
        return tuple(block for block in self.iter_blocks() if block.kind == kind)

    def visible_text(self) -> str:
        return "\n".join(atom for _, atom in self.visible_atoms)


def _iter_blocks(blocks: Iterable[ReportBlock]) -> Iterable[ReportBlock]:
    for block in blocks:
        yield block
        yield from _iter_blocks(block.children)


def _is_metadata(key: str) -> bool:
    # ``library_version`` is kept as a visible business-design qualifier (for
    # example, “Mercer 21 模式”); the remaining METADATA_KEYS are lineage or
    # renderer control fields and must not become report prose.
    return (key in METADATA_KEYS and key != "library_version") or key.endswith("_id") or key.endswith("_ids")


def _atom(value: Any) -> str | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return scalar(value)
    return None


def _visible_keys(records: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for item in records:
        for key in item:
            if not _is_metadata(key) and key not in keys:
                keys.append(key)
    return keys


def _table_allowed(records: list[dict[str, Any]], keys: list[str]) -> bool:
    if not records or not keys or len(keys) > 6:
        return False
    values = [scalar(item.get(key)) for item in records for key in keys]
    if any(isinstance(item.get(key), (dict, list)) for item in records for key in keys):
        return False
    average_length = sum(len(value) for value in values) / max(len(values), 1)
    return len(keys) <= 5 or average_length <= 45


def _record_table(records: list[dict[str, Any]], title: str, source_pointer: str, keys: list[str], *, role: str = "supporting") -> ReportBlock:
    rows = tuple(tuple(scalar(item.get(key)) for key in keys) for item in records)
    row_pointers = tuple(pointer(source_pointer, index) for index in range(len(records)))
    pointers = tuple(pointer(pointer(source_pointer, index), key) for index in range(len(records)) for key in keys if key in records[index])
    return ReportBlock(
        "compact_table", title, source_pointer, role=role, columns=tuple(label(key) for key in keys), rows=rows,
        row_pointers=row_pointers, source_pointers=pointers, presentation_hint="table-gate-approved",
    )


def _make_blocks(value: Any, title: str, source_pointer: str, *, semantic_kind: str | None = None,
                 role: str = "supporting", relation: str = "parallel", priority: int = 2) -> list[ReportBlock]:
    atom = _atom(value)
    if atom is not None:
        return [ReportBlock(semantic_kind or "scalar", title, source_pointer, role=role, relation=relation, priority=priority, value=atom)]
    if isinstance(value, dict):
        children: list[ReportBlock] = []
        for key, child in value.items():
            if _is_metadata(key):
                continue
            children.extend(_make_blocks(child, label(key), pointer(source_pointer, key)))
        return [ReportBlock(semantic_kind or "group", title, source_pointer, role=role, relation=relation, priority=priority, children=tuple(children), presentation_hint=semantic_kind or "group")]
    if isinstance(value, list):
        if not value:
            return [ReportBlock(semantic_kind or "scalar", title, source_pointer, role=role, value="无")]
        if all(isinstance(item, dict) for item in value):
            records = [item for item in value if isinstance(item, dict)]
            keys = _visible_keys(records)
            if _table_allowed(records, keys):
                table = _record_table(records, title, source_pointer, keys, role=role)
                if semantic_kind and semantic_kind in SEMANTIC_KINDS and semantic_kind != "compact_table":
                    return [ReportBlock(semantic_kind, title, source_pointer, role=role, relation=relation, priority=priority, children=(table,), presentation_hint="record-table")]
                return [table]
            cards: list[ReportBlock] = []
            for index, item in enumerate(records):
                card_title = f"{title} {index + 1}"
                for candidate in ("segment", "target", "name", "offer", "point", "dimension"):
                    if item.get(candidate):
                        card_title += f" · {scalar(item[candidate])}"
                        break
                children: list[ReportBlock] = []
                for key, child in item.items():
                    if _is_metadata(key):
                        continue
                    children.extend(_make_blocks(child, label(key), pointer(pointer(source_pointer, index), key)))
                cards.append(ReportBlock("record", card_title, pointer(source_pointer, index), role="supporting", children=tuple(children), presentation_hint="record-card"))
            return [ReportBlock(semantic_kind or "record_cards", title, source_pointer, role=role, relation=relation, priority=priority, children=tuple(cards), presentation_hint="record-cards")]
        children = []
        for index, child in enumerate(value):
            children.extend(_make_blocks(child, f"{title} {index + 1}", pointer(source_pointer, index)))
        return [ReportBlock(semantic_kind or "record_cards", title, source_pointer, role=role, children=tuple(children), presentation_hint="record-cards")]
    return [ReportBlock(semantic_kind or "fallback_group", title, source_pointer, role=role, value=scalar(value))]


def _split_record_field(value: Any, title: str, source_pointer: str, groups: tuple[tuple[str, tuple[str, ...]], ...], semantic_kind: str) -> ReportBlock:
    records = value if isinstance(value, list) else []
    children: list[ReportBlock] = []
    for group_title, keys in groups:
        present_keys = [key for key in keys if any(isinstance(item, dict) and key in item for item in records)]
        if present_keys:
            children.append(_record_table([item for item in records if isinstance(item, dict)], group_title, source_pointer, present_keys, role="supporting"))
    return ReportBlock(semantic_kind, title, source_pointer, role="evidence", relation="containment", priority=1, children=tuple(children), presentation_hint="semantic-table-split")


def _semantic_field(chapter: str, key: str, value: Any, source_pointer: str) -> list[ReportBlock]:
    if key == "key_message":
        return _make_blocks(value, "核心观点", source_pointer, semantic_kind="chapter_thesis", role="thesis", priority=1)
    kinds: dict[tuple[str, str], tuple[str, str, int]] = {
        ("market_scan", "five_looks"): ("record_cards", "insight", 2),
        ("market_scan", "policy"): ("record_cards", "evidence", 2),
        ("market_scan", "competitor_overview"): ("comparison", "evidence", 2),
        ("customer_selection", "current_position_assessment"): ("implication", "evidence", 2),
        ("customer_selection", "selection_method"): ("decision", "decision", 1),
        ("customer_selection", "segment_evaluation"): ("score_matrix", "evidence", 1),
        ("customer_selection", "recommended_segment"): ("decision", "decision", 1),
        ("customer_selection", "customer_segmentation"): ("record_cards", "evidence", 2),
        ("customer_selection", "high_value_targets"): ("record_cards", "decision", 1),
        ("customer_selection", "customer_needs_pains"): ("record_cards", "evidence", 2),
        ("value_proposition", "competitor_approaches"): ("comparison", "evidence", 2),
        ("value_proposition", "differentiated_offering"): ("recommendation", "decision", 1),
        ("profit_model", "pattern_screening"): ("comparison", "decision", 1),
        ("profit_model", "candidate_models"): ("comparison", "decision", 1),
        ("profit_model", "selected_architecture"): ("profit_architecture", "decision", 1),
        ("profit_model", "unit_economics"): ("metric", "evidence", 2),
        ("profit_model", "profitability_estimate"): ("metric", "evidence", 2),
        ("profit_model", "growth_and_funding_plan"): ("recommendation", "supporting", 2),
        ("profit_model", "validation_tests"): ("process", "decision", 2),
        ("scope_of_activities", "in_scope"): ("scope_boundary", "decision", 1),
        ("scope_of_activities", "out_of_scope"): ("scope_boundary", "decision", 1),
        ("strategic_control", "control_points"): ("control_mechanism", "decision", 1),
        ("risk_management", "risks"): ("risk_register", "evidence", 2),
    }
    if chapter == "profit_model" and key == "customer_value_equations":
        groups = (("客户价值来源", ("target_customer", "incremental_revenue", "avoided_loss", "working_capital_improvement", "risk_reduction", "adoption_cost")), ("价值验证", ("target_customer", "net_value_logic", "value_metric")))
        return [_split_record_field(value, "客户价值等式", source_pointer, groups, "value_equation")]
    if chapter == "profit_model" and key == "value_capture_mechanisms":
        groups = (("提供物与客户价值", ("offer", "target_customer", "value_created", "value_metric")), ("付费与合同", ("offer", "payer", "charging_unit", "price_formula", "pricing_mechanism", "contract_and_risk_sharing")), ("收入、利润与控制", ("offer", "revenue_timing", "margin_logic", "control_point")))
        return [_split_record_field(value, "价值获取机制", source_pointer, groups, "value_capture")]
    kind, role, priority = kinds.get((chapter, key), (None, "supporting", 2))
    return _make_blocks(value, label(key), source_pointer, semantic_kind=kind, role=role, priority=priority)


def _collect_ids(value: Any, key: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == key and isinstance(child, list):
                for item in child:
                    if isinstance(item, str) and item not in out:
                        out.append(item)
            _collect_ids(child, key, out)
    elif isinstance(value, list):
        for child in value:
            _collect_ids(child, key, out)


def _collect_atoms(value: Any, source_pointer: str = "") -> list[tuple[str, str]]:
    atoms: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if _is_metadata(key):
                continue
            atoms.extend(_collect_atoms(child, pointer(source_pointer, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            atoms.extend(_collect_atoms(child, pointer(source_pointer, index)))
    elif isinstance(value, (str, int, float, bool)):
        text = scalar(value)
        if text.strip():
            atoms.append((source_pointer, text))
    return atoms


def build_report(data: dict[str, Any], *, source_name: str = "business_design.json", source_sha256: str = "") -> ReportDocument:
    sections: list[ReportSection] = []
    summary_blocks: list[ReportBlock] = []
    if "story_line" in data:
        summary_blocks.extend(_make_blocks(data["story_line"], "核心判断", "/story_line", semantic_kind="executive_thesis", role="thesis", priority=1))
    context_children: list[ReportBlock] = []
    for key in ("company", "industry", "strategic_intent", "core_pain"):
        if key in data:
            context_children.extend(_make_blocks(data[key], label(key), pointer("", key), semantic_kind="metric" if key in {"company", "industry"} else "implication", role="supporting", priority=2))
    known_root = {"company", "industry", "strategic_intent", "core_pain", "story_line", "chapters", "assumptions", "data_gaps"}
    for key, value in data.items():
        if key not in known_root and not _is_metadata(key):
            context_children.extend(_make_blocks(value, label(key), pointer("", key), role="supporting", priority=2))
    summary_blocks.append(ReportBlock("summary_context", "战略背景", "", role="supporting", children=tuple(context_children), presentation_hint="summary-context"))
    chapter_conclusions: list[ReportBlock] = []
    for chapter_key, chapter_title in CHAPTER_NAMES.items():
        chapter = data.get("chapters", {}).get(chapter_key, {}) if isinstance(data.get("chapters"), dict) else {}
        if isinstance(chapter, dict) and "key_message" in chapter:
            # The summary reuses the same source values as executive-thesis
            # cards; chapter sections own the seven canonical chapter_thesis
            # nodes, so the semantic hard gate remains exactly 7.
            chapter_conclusions.extend(_make_blocks(chapter["key_message"], chapter_title, pointer(pointer("/chapters", chapter_key), "key_message"), semantic_kind="executive_thesis", role="thesis", priority=1))
    summary_blocks.append(ReportBlock("design_conclusions", "七项设计结论", "", role="thesis", relation="parallel", priority=1, children=tuple(chapter_conclusions), presentation_hint="decision-summary-grid"))
    sections.append(ReportSection("summary", "执行摘要", "", tuple(summary_blocks)))
    sections.append(ReportSection("scope", "研究范围与证据口径", "", (ReportBlock("note", "研究口径", "", role="supporting", value="本报告的业务观点、数字、事实、估算、假设和数据缺口均来自当前 business_design.json；各章节通过 evidence IDs 与 assumption IDs 保留回溯关系。"),)))
    sections.append(ReportSection("assumptions", "关键假设与验证计划", "/assumptions", tuple(_make_blocks(data.get("assumptions", []), "关键假设", "/assumptions", semantic_kind="assumption", role="condition", priority=2))))
    chapters = data.get("chapters", {}) if isinstance(data.get("chapters"), dict) else {}
    for chapter_key, chapter_title in CHAPTER_NAMES.items():
        chapter = chapters.get(chapter_key, {})
        blocks: list[ReportBlock] = []
        if isinstance(chapter, dict):
            for field_key, child in chapter.items():
                if _is_metadata(field_key):
                    continue
                blocks.extend(_semantic_field(chapter_key, field_key, child, pointer(pointer("/chapters", chapter_key), field_key)))
        sections.append(ReportSection(chapter_key, chapter_title, pointer("/chapters", chapter_key), tuple(blocks)))
    sections.append(ReportSection("data_gaps", "数据缺口", "/data_gaps", tuple(_make_blocks(data.get("data_gaps", []), "数据缺口明细", "/data_gaps", semantic_kind="data_gap", role="condition", priority=2))))
    evidence: list[str] = []
    assumptions: list[str] = []
    _collect_ids(data, "evidence_ids", evidence)
    _collect_ids(data, "assumption_ids", assumptions)
    sections.append(ReportSection("evidence_index", "证据索引", "", (ReportBlock("source_index", "本业务设计引用的证据 IDs", "", value=", ".join(sorted(evidence)) or "无"),)))
    sections.append(ReportSection("assumption_index", "假设索引", "", (ReportBlock("source_index", "本业务设计引用的假设 IDs", "", value=", ".join(sorted(assumptions)) or "无"),)))
    return ReportDocument(source_name, source_sha256, scalar(data.get("company")), tuple(sections), tuple(sorted(evidence)), tuple(sorted(assumptions)), tuple(_collect_atoms(data)))
