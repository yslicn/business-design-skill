#!/usr/bin/env python3
"""Validate business-design JSON artifacts and their cross-file references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from content_projection import (
        business_visible_atoms,
        NUMERIC_TOKEN_PATTERN,
        numeric_tokens,
        qualifier_tokens,
        slide_blocks_visible_projection,
    )
except ModuleNotFoundError:  # Support importlib-based tests and embedding.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from content_projection import (  # type: ignore[no-redef]
        business_visible_atoms,
        NUMERIC_TOKEN_PATTERN,
        numeric_tokens,
        qualifier_tokens,
        slide_blocks_visible_projection,
    )


SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_DIR = SKILL_DIR / "schemas"
DEFAULT_WEIGHTS = {
    "profit_pool_size": 0.20,
    "growth_and_value_migration": 0.20,
    "competitive_attractiveness": 0.15,
    "capability_fit": 0.20,
    "business_synergy": 0.15,
    "feasibility_and_risk": 0.10,
}
MARKET_DIMENSIONS = (
    "profit_pool_size",
    "growth_and_value_migration",
    "competitive_attractiveness",
)
ENTERPRISE_DIMENSIONS = (
    "capability_fit",
    "business_synergy",
    "feasibility_and_risk",
)
SKIP_COVERAGE_KEYS = {"evidence_ids", "assumption_ids"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 JSON {path}: {exc}") from exc


def iter_key_values(value: Any, key: str) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if child_key == key:
                yield child_key, child_value
            yield from iter_key_values(child_value, key)
    elif isinstance(value, list):
        for child in value:
            yield from iter_key_values(child, key)


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def duplicate_ids(items: list[Any], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id in seen:
            errors.append(f"{label} 存在重复 ID: {item_id}")
        if isinstance(item_id, str):
            seen.add(item_id)
    return errors


def flatten_strings(value: Any) -> str:
    strings: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            strings.append(node)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(value)
    return "\n".join(strings)


def normalize_text(value: Any) -> str:
    text = str(value)
    translations = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "＋": "+"})
    return re.sub(r"\s+", "", text.translate(translations)).lower()


def visible_values(value: Any) -> list[str]:
    """Backward-compatible wrapper around the explicit slide projection."""

    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return slide_blocks_visible_projection(value)
    if isinstance(value, dict):
        return slide_blocks_visible_projection([value])
    return [str(value)] if isinstance(value, (str, int, float, bool)) else []


def semantic_atoms(value: Any) -> list[str]:
    """Return visible business-content atoms, excluding traceability metadata."""
    # Keep this public helper's historical broad traversal for authoring/tests;
    # fidelity checks use business_visible_atoms() below, which is stricter.
    atoms: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key not in SKIP_COVERAGE_KEYS and key != "pattern_origin":
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, (str, int, float, bool)):
            text = str(node).strip()
            if text:
                atoms.append(text)

    walk(value)
    return atoms


def atom_fragments(atom: str) -> list[str]:
    """Split long prose so table restructuring can still pass exact-content checks."""
    normalized = normalize_text(atom)
    if len(normalized) <= 40:
        return [normalized]
    parts = [normalize_text(part) for part in re.split(r"[。；;\n]", atom)]
    return [part for part in parts if len(part) >= 4] or [normalized]


def missing_atoms(source: Any, target_blocks: list[dict[str, Any]]) -> list[str]:
    target_values = [normalize_text(value) for value in visible_values(target_blocks)]
    target_joined = "".join(target_values)
    target_numbers = numeric_tokens("\n".join(target_values))
    target_qualifiers = set(qualifier_tokens("\n".join(target_values)))
    missing: list[str] = []
    for atom in business_visible_atoms(source):
        fragments = atom_fragments(atom)
        source_numbers = numeric_tokens(atom)
        source_qualifiers = set(qualifier_tokens(atom))

        def fragment_present(fragment: str) -> bool:
            if fragment in target_joined or any(fragment in value for value in target_values):
                return True
            # Permit only deterministic numeric equivalence (e.g. 0.55 ↔ 55%)
            # while preserving units, qualifiers, and all other text.
            fragment_numbers = numeric_tokens(fragment)
            fragment_qualifiers = set(qualifier_tokens(fragment))
            stripped_fragment = NUMERIC_TOKEN_PATTERN.sub("", fragment)
            stripped_target = NUMERIC_TOKEN_PATTERN.sub("", target_joined)
            if stripped_fragment and stripped_fragment not in stripped_target:
                return False
            if not fragment_qualifiers.issubset(target_qualifiers):
                return False
            target_counter = Counter(target_numbers)
            return not (Counter(fragment_numbers) - target_counter)

        if not all(fragment_present(fragment) for fragment in fragments):
            missing.append(atom)
            continue
        if source_numbers and Counter(source_numbers) - Counter(target_numbers):
            missing.append(atom)
            continue
        if not source_qualifiers.issubset(target_qualifiers):
            missing.append(atom)
    return missing


def compound_marker_count(text: str) -> int:
    """Count explicit signs that prose contains several presentable ideas."""
    return len(
        re.findall(
            r"[；;]|(?:^|[\s，,。；;])(?:\(?[一二三四五六七八九十\d]+[)）\.、])|→|⇒|->",
            text,
        )
    )


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not part.isdigit():
                raise KeyError(pointer)
            index = int(part)
            if index >= len(current):
                raise KeyError(pointer)
            current = current[index]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(pointer)
    return current


def business_coverage_units(data: Any) -> dict[str, str]:
    """Return source units that must be explicitly placed or omitted.

    Values are the minimum required importance. Direct chapter components are
    intentionally used as the unit so coverage stays practical for small models.
    """
    units: dict[str, str] = {
        "/strategic_intent": "mandatory",
        "/core_pain": "mandatory",
        "/story_line": "mandatory",
    }
    if not isinstance(data, dict):
        return units

    for root_key in ("company", "industry"):
        if root_key in data:
            units[f"/{root_key}"] = "mandatory"

    for index, _ in enumerate(as_list(data.get("assumptions"))):
        units[f"/assumptions/{index}"] = "mandatory"
    for index, _ in enumerate(as_list(data.get("data_gaps"))):
        units[f"/data_gaps/{index}"] = "mandatory"

    chapters = data.get("chapters")
    if not isinstance(chapters, dict):
        return units
    for chapter_name, chapter in chapters.items():
        if not isinstance(chapter, dict):
            continue
        chapter_base = f"/chapters/{chapter_name}"
        if "key_message" in chapter:
            units[f"{chapter_base}/key_message"] = "mandatory"
        for key, value in chapter.items():
            if key == "key_message" or key in SKIP_COVERAGE_KEYS:
                continue
            base = f"{chapter_base}/{key}"
            if isinstance(value, list):
                for index, _ in enumerate(value):
                    mandatory_customer_lists = {"segment_evaluation"}
                    units[f"{base}/{index}"] = "mandatory" if (
                        chapter_name == "profit_model"
                        or (chapter_name == "customer_selection" and key in mandatory_customer_lists)
                    ) else "important"
            elif isinstance(value, dict) or isinstance(value, str):
                mandatory_customer_objects = {"selection_method", "recommended_segment"}
                units[base] = "mandatory" if (
                    chapter_name == "profit_model"
                    or (chapter_name == "customer_selection" and key in mandatory_customer_objects)
                ) else "important"
    return units


def required_placement(pointer: str) -> str | None:
    if pointer.startswith("/assumptions/") or pointer.startswith("/data_gaps/"):
        return "appendix"
    main_prefixes = (
        "/chapters/customer_selection/selection_method",
        "/chapters/customer_selection/segment_evaluation/",
        "/chapters/customer_selection/recommended_segment",
        "/chapters/profit_model/",
    )
    if pointer in {"/company", "/industry", "/strategic_intent", "/core_pain", "/story_line"}:
        return "main_deck"
    if pointer.endswith("/key_message") or pointer.startswith(main_prefixes):
        return "main_deck"
    return None


def validate_with_schema(data: Any, schema_name: str) -> tuple[list[str], list[str]]:
    try:
        from jsonschema import Draft7Validator
    except ImportError:
        return ["未安装 jsonschema，无法完成 JSON Schema 校验"], []

    schema = load_json(SCHEMA_DIR / schema_name)
    validator = Draft7Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")
    return errors, []


def validate_market(data: Any) -> list[str]:
    errors, warnings = validate_with_schema(data, "market_insight.schema.json")
    for warning in warnings:
        print(f"[WARN] {warning}")

    if not isinstance(data, dict):
        return errors + ["market_insight.json 顶层必须是对象"]

    sources = as_list(data.get("sources"))
    evidence = as_list(data.get("evidence_registry"))
    errors.extend(duplicate_ids(sources, "sources"))
    errors.extend(duplicate_ids(evidence, "evidence_registry"))

    source_ids = {item.get("id") for item in sources if isinstance(item, dict)}
    evidence_ids = {item.get("id") for item in evidence if isinstance(item, dict)}
    source_urls: dict[Any, Any] = {}
    seen_urls: dict[str, Any] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = source.get("id")
        url = source.get("url")
        source_urls[source_id] = url
        if isinstance(url, str):
            if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
                errors.append(f"来源 {source_id} URL 必须为可访问的 http(s) 地址: {url}")
            normalized_url = url.strip().lower().rstrip("/")
            if normalized_url in seen_urls:
                errors.append(
                    f"来源 {source_id} 与 {seen_urls[normalized_url]} 使用重复 URL，不能作为独立来源"
                )
            else:
                seen_urls[normalized_url] = source_id

    for _, values in iter_key_values(data, "source_ids"):
        if isinstance(values, list):
            for source_id in values:
                if source_id not in source_ids:
                    errors.append(f"悬空 source_id: {source_id}")

    for _, values in iter_key_values(data, "evidence_ids"):
        if isinstance(values, list):
            for evidence_id in values:
                if evidence_id not in evidence_ids:
                    errors.append(f"悬空 evidence_id: {evidence_id}")
    for item in evidence:
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("id", "<unknown>")
        linked_sources = as_list(item.get("source_ids"))
        if item.get("evidence_type") == "triangulated":
            if len(linked_sources) < 2:
                errors.append(f"{evidence_id} 标记 triangulated，但少于两个来源")
            distinct_urls = {
                str(source_urls.get(source_id, "")).strip().lower().rstrip("/")
                for source_id in linked_sources
                if source_urls.get(source_id)
            }
            if len(distinct_urls) < 2:
                errors.append(f"{evidence_id} 标记 triangulated，但没有两个独立来源 URL")
        if item.get("evidence_type") == "estimated" and not str(
            item.get("calculation_or_basis", "")
        ).strip():
            errors.append(f"{evidence_id} 为 estimated，但缺少可复算 calculation_or_basis")
    return errors


def validate_insight_review(data: Any) -> list[str]:
    errors, warnings = validate_with_schema(data, "insight_review.schema.json")
    for warning in warnings:
        print(f"[WARN] {warning}")
    if not isinstance(data, dict):
        return errors + ["insight_review.json 顶层必须是对象"]

    report_length = data.get("report_length")
    if isinstance(report_length, dict):
        count = report_length.get("effective_count")
        in_range = isinstance(count, int) and 10_000 <= count <= 15_000
        if report_length.get("passed") != in_range:
            errors.append("insight_review.report_length.passed 与 10000-15000 字实际范围不一致")

    if data.get("status") == "PASS":
        boolean_groups = {
            "research_coverage": data.get("research_coverage"),
            "data_integrity": data.get("data_integrity"),
            "business_design_readiness": data.get("business_design_readiness"),
        }
        for group_name, group in boolean_groups.items():
            if not isinstance(group, dict):
                continue
            for field, value in group.items():
                if isinstance(value, bool) and not value:
                    errors.append(f"insight_review status=PASS，但 {group_name}.{field}=false")
        integrity = data.get("data_integrity")
        if isinstance(integrity, dict):
            if as_list(integrity.get("suspected_fabrications")):
                errors.append("insight_review status=PASS，但仍存在 suspected_fabrications")
            if as_list(integrity.get("unsupported_claims")):
                errors.append("insight_review status=PASS，但仍存在 unsupported_claims")
        if data.get("schema_version") != "1.1" and isinstance(report_length, dict) and not report_length.get("passed"):
            errors.append("insight_review status=PASS，但研究报告字数不合格")
        blocking_issues = [
            item
            for item in as_list(data.get("issues"))
            if isinstance(item, dict) and item.get("severity") in {"blocking", "major"}
        ]
        if blocking_issues:
            errors.append("insight_review status=PASS，但仍存在 blocking/major 问题")
    else:
        errors.append(
            f"市场洞察输入质量门未通过: status={data.get('status')}，route={data.get('revision_route')}"
        )
    return errors


def validate_business(data: Any, market: Any | None) -> list[str]:
    errors, warnings = validate_with_schema(data, "business_design.schema.json")
    for warning in warnings:
        print(f"[WARN] {warning}")

    if not isinstance(data, dict):
        return errors + ["business_design.json 顶层必须是对象"]

    assumptions = as_list(data.get("assumptions"))
    errors.extend(duplicate_ids(assumptions, "assumptions"))
    assumption_ids = {item.get("id") for item in assumptions if isinstance(item, dict)}

    for _, values in iter_key_values(data, "assumption_ids"):
        if isinstance(values, list):
            for assumption_id in values:
                if assumption_id not in assumption_ids:
                    errors.append(f"悬空 assumption_id: {assumption_id}")

    if market is None:
        errors.append("校验 business_design.json 时必须同时提供 --market")
    elif not isinstance(market, dict):
        errors.append("market_insight.json 顶层必须是对象")
    else:
        known_evidence = {
            item.get("id")
            for item in as_list(market.get("evidence_registry"))
            if isinstance(item, dict)
        }
        for _, values in iter_key_values(data, "evidence_ids"):
            if isinstance(values, list):
                for evidence_id in values:
                    if evidence_id not in known_evidence:
                        errors.append(f"business_design 中悬空 evidence_id: {evidence_id}")

    chapters = data.get("chapters")
    customer_selection = chapters.get("customer_selection") if isinstance(chapters, dict) else None
    selection_method = (
        customer_selection.get("selection_method")
        if isinstance(customer_selection, dict)
        else None
    )
    weights = (
        selection_method.get("dimension_weights")
        if isinstance(selection_method, dict)
        else None
    )
    if not isinstance(weights, dict):
        weights = DEFAULT_WEIGHTS
    else:
        all_weight = sum(value for value in weights.values() if isinstance(value, (int, float)))
        market_weight = selection_method.get("market_attractiveness_weight")
        enterprise_weight = selection_method.get("enterprise_fit_weight")
        market_dimensions_weight = sum(weights.get(name, 0) for name in MARKET_DIMENSIONS)
        enterprise_dimensions_weight = sum(weights.get(name, 0) for name in ENTERPRISE_DIMENSIONS)
        if abs(all_weight - 1.0) > 0.001:
            errors.append(f"selection_method 六维权重之和应为 1，当前为 {all_weight:.4f}")
        if not isinstance(market_weight, (int, float)) or not isinstance(enterprise_weight, (int, float)):
            errors.append("selection_method 缺少市场吸引力/企业胜任权权重")
        else:
            if abs(market_weight + enterprise_weight - 1.0) > 0.001:
                errors.append("市场吸引力权重 + 企业胜任权权重必须等于 1")
            if abs(market_dimensions_weight - market_weight) > 0.001:
                errors.append(
                    f"市场吸引力三个维度权重之和应为 {market_weight:.2f}，当前为 {market_dimensions_weight:.2f}"
                )
            if abs(enterprise_dimensions_weight - enterprise_weight) > 0.001:
                errors.append(
                    f"企业胜任权三个维度权重之和应为 {enterprise_weight:.2f}，当前为 {enterprise_dimensions_weight:.2f}"
                )
    evaluations = as_list(
        customer_selection.get("segment_evaluation")
        if isinstance(customer_selection, dict)
        else None
    )
    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            continue
        scores = evaluation.get("scores", {})
        if not all(name in scores for name in weights):
            continue
        expected_market = round(sum(scores[name] * weights[name] for name in MARKET_DIMENSIONS), 2)
        expected_enterprise = round(sum(scores[name] * weights[name] for name in ENTERPRISE_DIMENSIONS), 2)
        expected = round(expected_market + expected_enterprise, 2)
        actual_market = evaluation.get("market_attractiveness_contribution")
        actual_enterprise = evaluation.get("enterprise_fit_contribution")
        actual = evaluation.get("weighted_score")
        segment = evaluation.get("segment", "<unknown>")
        if not isinstance(actual_market, (int, float)) or abs(actual_market - expected_market) > 0.01:
            errors.append(
                f"{segment} market_attractiveness_contribution 应为 {expected_market}，当前为 {actual_market}"
            )
        if not isinstance(actual_enterprise, (int, float)) or abs(actual_enterprise - expected_enterprise) > 0.01:
            errors.append(
                f"{segment} enterprise_fit_contribution 应为 {expected_enterprise}，当前为 {actual_enterprise}"
            )
        if not isinstance(actual, (int, float)) or abs(actual - expected) > 0.01:
            errors.append(
                f"{segment} weighted_score 应为 {expected}，当前为 {actual}"
            )

    profit_model = chapters.get("profit_model") if isinstance(chapters, dict) else None
    if isinstance(profit_model, dict):
        candidates = as_list(profit_model.get("candidate_models"))
        errors.extend(duplicate_ids(candidates, "profit_model.candidate_models"))
        candidate_ids = {
            item.get("id") for item in candidates if isinstance(item, dict)
        }
        screening = profit_model.get("pattern_screening")
        if isinstance(screening, dict):
            for model_id in as_list(screening.get("shortlisted_model_ids")):
                if model_id not in candidate_ids:
                    errors.append(f"pattern_screening 引用了不存在的候选模式: {model_id}")
            if set(as_list(screening.get("shortlisted_model_ids"))) != candidate_ids:
                errors.append("pattern_screening.shortlisted_model_ids 必须与 candidate_models ID 完全一致")
        value_equations = as_list(profit_model.get("customer_value_equations"))
        errors.extend(duplicate_ids(value_equations, "profit_model.customer_value_equations"))
        value_equation_ids = {
            item.get("id") for item in value_equations if isinstance(item, dict)
        }
        selected = profit_model.get("selected_architecture")
        selected_ids: list[Any] = []
        if isinstance(selected, dict):
            selected_ids = [selected.get("primary_model_id")]
            selected_ids.extend(as_list(selected.get("supporting_model_ids")))
            if len(selected_ids) != len(set(selected_ids)):
                errors.append("selected_architecture 主模式与辅助模式 ID 不得重复")
            for model_id in selected_ids:
                if model_id not in candidate_ids:
                    errors.append(f"selected_architecture 引用了不存在的候选模式: {model_id}")
            for model_id in selected_ids:
                model = next(
                    (
                        item
                        for item in candidates
                        if isinstance(item, dict) and item.get("id") == model_id
                    ),
                    None,
                )
                if isinstance(model, dict) and model.get("fit") == "rejected":
                    errors.append(f"selected_architecture 不能选择 rejected 候选: {model_id}")
        mechanisms = as_list(profit_model.get("value_capture_mechanisms"))
        errors.extend(duplicate_ids(mechanisms, "profit_model.value_capture_mechanisms"))
        linked_models: set[Any] = set()
        linked_equations: set[Any] = set()
        for mechanism in mechanisms:
            if not isinstance(mechanism, dict):
                continue
            mechanism_id = mechanism.get("id", "<unknown>")
            for model_id in as_list(mechanism.get("linked_model_ids")):
                linked_models.add(model_id)
                if model_id not in candidate_ids:
                    errors.append(f"{mechanism_id} 引用了不存在的候选模式: {model_id}")
                if selected_ids and model_id not in selected_ids:
                    errors.append(f"{mechanism_id} 关联了未入选利润模式: {model_id}")
            for equation_id in as_list(mechanism.get("linked_value_equation_ids")):
                linked_equations.add(equation_id)
                if equation_id not in value_equation_ids:
                    errors.append(f"{mechanism_id} 引用了不存在的客户价值等式: {equation_id}")
        for model_id in selected_ids:
            if model_id not in linked_models:
                errors.append(f"入选利润模式未落到任何价值获取机制: {model_id}")
        for equation_id in value_equation_ids:
            if equation_id not in linked_equations:
                errors.append(f"客户价值等式未落到任何价值获取机制: {equation_id}")
    return errors


def _directed_graph(node_ids: set[str], links: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    outgoing = {node_id: set() for node_id in node_ids}
    incoming = {node_id: set() for node_id in node_ids}
    for link in links:
        source = link.get("from")
        target = link.get("to")
        if source in node_ids and target in node_ids and source != target:
            outgoing[source].add(target)
            incoming[target].add(source)
    return outgoing, incoming


def _reachable_from(starts: set[str], outgoing: dict[str, set[str]]) -> set[str]:
    reached: set[str] = set()
    pending = list(starts)
    while pending:
        node_id = pending.pop()
        if node_id in reached:
            continue
        reached.add(node_id)
        pending.extend(outgoing.get(node_id, set()) - reached)
    return reached


def validate_structure_relations(
    page_id: str,
    logic: str | None,
    nodes: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    links: list[dict[str, Any]],
) -> list[str]:
    """Validate graph/group relationships beyond schema-level existence checks."""

    errors: list[str] = []
    node_ids = {node.get("node_id") for node in nodes if isinstance(node.get("node_id"), str)}
    primary_ids = {
        node.get("node_id")
        for node in nodes
        if node.get("role") == "primary" and isinstance(node.get("node_id"), str)
    }
    group_membership: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for group in groups:
        group_id = group.get("group_id", "<unknown>")
        group_nodes = [node_id for node_id in as_list(group.get("node_ids")) if node_id in node_ids]
        if not group_nodes:
            errors.append(f"{page_id} semantic group {group_id} 不能是空 group")
        for node_id in group_nodes:
            group_membership.setdefault(node_id, []).append(str(group_id))

    if logic in {"comparison", "matrix", "portfolio"}:
        if len(groups) < 2:
            errors.append(f"{page_id} visual_intent.logic={logic} 至少需要 2 个 semantic groups")
        uncovered = primary_ids - {node_id for node_id, memberships in group_membership.items() if memberships}
        if uncovered:
            errors.append(f"{page_id} {logic} primary semantic node 未被任何 group 覆盖: {sorted(uncovered)}")
        duplicated = {
            node_id: memberships
            for node_id, memberships in group_membership.items()
            if node_id in primary_ids and len(memberships) > 1
        }
        if duplicated:
            errors.append(f"{page_id} {logic} 互斥 group 重复纳入 primary node: {duplicated}")

    outgoing, incoming = _directed_graph(node_ids, links)
    if logic in {"process", "timeline"}:
        if len(primary_ids) < 2:
            errors.append(f"{page_id} visual_intent.logic={logic} 至少需要 2 个 primary semantic nodes")
        isolated = {
            node_id
            for node_id in primary_ids
            if not (outgoing.get(node_id) or incoming.get(node_id))
        }
        if isolated:
            errors.append(f"{page_id} {logic} 存在孤立 primary node: {sorted(isolated)}")
        roots = {node_id for node_id in primary_ids if not (incoming.get(node_id) & primary_ids)}
        reached = _reachable_from(roots, outgoing)
        if not roots or not primary_ids.issubset(reached):
            errors.append(f"{page_id} {logic} links 未形成可遍历的有向链: roots={sorted(roots)}, reached={sorted(reached)}")

    if logic == "hierarchy":
        roots = {node_id for node_id in primary_ids if not (incoming.get(node_id) & primary_ids)}
        if len(roots) < 1:
            errors.append(f"{page_id} hierarchy 必须存在至少一个入度为 0 的根节点")
        reached = _reachable_from(roots, outgoing)
        if not primary_ids.issubset(reached):
            errors.append(f"{page_id} hierarchy 存在无法从根节点到达的 primary node: {sorted(primary_ids - reached)}")
        if len(roots) > 1 and len(primary_ids) > 1:
            errors.append(f"{page_id} hierarchy 存在多个未建立包含关系的根节点: {sorted(roots)}")

    if logic == "bridge":
        roots = {node_id for node_id in primary_ids if not (incoming.get(node_id) & primary_ids)}
        sinks = {node_id for node_id in primary_ids if not (outgoing.get(node_id) & primary_ids)}
        reachable = _reachable_from(roots, outgoing)
        has_distinct_path = any(
            root != sink and sink in reachable
            for root in roots
            for sink in sinks
        )
        if not roots or not sinks or not has_distinct_path:
            errors.append(f"{page_id} bridge 无法识别从起点到终点的路径: roots={sorted(roots)}, sinks={sorted(sinks)}")

    if logic == "parallel":
        if len(primary_ids) < 2:
            errors.append(f"{page_id} parallel 至少需要 2 个同层 primary semantic nodes")
        if links:
            print(f"[WARN] {page_id} visual_intent.logic=parallel 却声明了方向 links；请确认关系类型是否应为 process/bridge")
    return errors


def validate_slides(data: Any, business: Any | None, market: Any | None) -> list[str]:
    errors, warnings = validate_with_schema(data, "slide_input.schema.json")
    for warning in warnings:
        print(f"[WARN] {warning}")
    if not isinstance(data, dict):
        return errors + ["slide_input.json 顶层必须是对象"]

    schema_version = data.get("schema_version")
    if schema_version in {"1.1", "1.2"}:
        print(
            f"[WARN] slide_input schema {schema_version} 为兼容模式；"
            "新项目必须迁移到 1.3 语义原子与关系契约"
        )

    pages = as_list(data.get("pages"))
    page_ids: set[str] = set()
    sequences: list[int] = []
    block_ids: set[str] = set()
    unit_ids: set[str] = set()
    appendix_kinds: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_id = page.get("page_id")
        if page_id in page_ids:
            errors.append(f"slide_input 存在重复 page_id: {page_id}")
        if isinstance(page_id, str):
            page_ids.add(page_id)
        if isinstance(page.get("sequence"), int):
            sequences.append(page["sequence"])
        if page.get("page_type") == "appendix" and isinstance(page.get("appendix_kind"), str):
            appendix_kinds.add(page["appendix_kind"])
        page_blocks = [
            block for block in as_list(page.get("content_blocks")) if isinstance(block, dict)
        ]
        page_block_ids = {
            block.get("block_id") for block in page_blocks if isinstance(block.get("block_id"), str)
        }
        composition = page.get("composition")
        if schema_version in {"1.2", "1.3"} and not isinstance(composition, dict):
            errors.append(f"{page_id} 缺少 composition，无法约束同页组合与最大拆页数")
        if isinstance(composition, dict):
            policy = composition.get("grouping_policy")
            max_slides = composition.get("max_rendered_slides")
            primary_ids = set(as_list(composition.get("primary_block_ids")))
            missing_primary = primary_ids - page_block_ids
            if missing_primary:
                errors.append(f"{page_id} composition 引用了不存在的 primary block: {sorted(missing_primary)}")
            if policy == "keep_together" and max_slides != 1:
                errors.append(f"{page_id} keep_together 的 max_rendered_slides 必须为 1")
            if policy == "splittable" and isinstance(max_slides, int) and max_slides < 2:
                errors.append(f"{page_id} splittable 的 max_rendered_slides 必须至少为 2")
            if isinstance(max_slides, int) and max_slides > 1 and not composition.get("split_rationale"):
                errors.append(f"{page_id} 允许拆成多页时必须提供 split_rationale")
            if page.get("page_type") in {"cover", "section"} and max_slides != 1:
                errors.append(f"{page_id} 封面/章节页必须保持单页")

        requires_lineage = page.get("page_type") != "cover" and page.get(
            "appendix_kind"
        ) != "evidence_mapping"
        primary_role_ids: set[str] = set()
        visible_role_count = 0
        required_content_refs: set[str] = set()
        allowed_content_refs: set[str] = set()
        for block in page_blocks:
            block_id = block.get("block_id")
            if block_id in block_ids:
                errors.append(f"slide_input 存在重复 block_id: {block_id}")
            if isinstance(block_id, str):
                block_ids.add(block_id)
            display_role = block.get("display_role")
            if schema_version in {"1.2", "1.3"} and display_role is None:
                errors.append(f"{block_id} 缺少 display_role，无法判断主展项与辅助说明")
            if display_role == "primary" and isinstance(block_id, str):
                primary_role_ids.add(block_id)
            if display_role in {"primary", "supporting"}:
                visible_role_count += 1
            source_pointers = as_list(block.get("source_pointers"))
            if requires_lineage and not source_pointers:
                errors.append(f"{block_id} 缺少 source_pointers，无法追溯 business_design.json")
            if isinstance(business, dict):
                for pointer in source_pointers:
                    try:
                        resolve_json_pointer(business, pointer)
                    except KeyError:
                        errors.append(f"{block_id} source_pointer 不存在: {pointer}")
            table = block.get("table")
            if isinstance(table, dict):
                columns = as_list(table.get("columns"))
                for row_index, row in enumerate(as_list(table.get("rows"))):
                    if isinstance(row, list) and len(row) != len(columns):
                        errors.append(
                            f"{block_id} table 第 {row_index + 1} 行列数 {len(row)} != 表头列数 {len(columns)}"
                        )
            chart = block.get("chart")
            if isinstance(chart, dict):
                categories = as_list(chart.get("categories"))
                for series in as_list(chart.get("series")):
                    if isinstance(series, dict) and len(as_list(series.get("values"))) != len(categories):
                        errors.append(
                            f"{block_id} chart series {series.get('name')} 数值数量与 categories 不一致"
                        )

            semantic_units = [
                unit
                for unit in as_list(block.get("semantic_units"))
                if isinstance(unit, dict)
            ]
            if semantic_units:
                if schema_version == "1.3" and any(
                    key in block for key in ("body", "items", "table", "chart", "kpis")
                ):
                    errors.append(
                        f"{block_id} semantic_units 不得与 body/items/table/chart/kpis 混装；"
                        "请拆成独立 block"
                    )
                block_unit_ids: set[str] = set()
                unit_pointer_union: set[str] = set()
                for unit in semantic_units:
                    unit_id = unit.get("unit_id")
                    if unit_id in unit_ids or unit_id in block_unit_ids:
                        errors.append(f"slide_input 存在重复 semantic unit_id: {unit_id}")
                    if isinstance(unit_id, str):
                        unit_ids.add(unit_id)
                        block_unit_ids.add(unit_id)
                        allowed_content_refs.add(unit_id)
                        if display_role in {"primary", "supporting"}:
                            required_content_refs.add(unit_id)
                    unit_pointers = set(as_list(unit.get("source_pointers")))
                    unit_pointer_union.update(unit_pointers)
                    if requires_lineage and not unit_pointers:
                        errors.append(f"{unit_id} 缺少 source_pointers，无法原子级追溯")
                    undeclared_pointers = unit_pointers - set(source_pointers)
                    if undeclared_pointers:
                        errors.append(
                            f"{unit_id} source_pointers 未在所属 block {block_id} 声明: "
                            f"{sorted(undeclared_pointers)}"
                        )
                    undeclared_evidence = set(as_list(unit.get("evidence_ids"))) - set(
                        as_list(page.get("evidence_ids"))
                    )
                    if undeclared_evidence:
                        errors.append(
                            f"{unit_id} evidence_ids 未在页面 {page_id} 声明: "
                            f"{sorted(undeclared_evidence)}"
                        )
                    undeclared_assumptions = set(as_list(unit.get("assumption_ids"))) - set(
                        as_list(page.get("assumption_ids"))
                    )
                    if undeclared_assumptions:
                        errors.append(
                            f"{unit_id} assumption_ids 未在页面 {page_id} 声明: "
                            f"{sorted(undeclared_assumptions)}"
                        )
                    if schema_version == "1.3" and page.get("page_type") in {"content", "summary"}:
                        headline = str(unit.get("headline", ""))
                        detail = str(unit.get("detail", ""))
                        if len(normalize_text(headline)) > 60:
                            errors.append(f"{unit_id} headline 超过 60 字，仍是正文而非可扫读标签")
                        if len(normalize_text(detail)) > 220 or compound_marker_count(detail) >= 3:
                            errors.append(f"{unit_id} detail 仍包含过多原子观点，必须继续拆分")
                if schema_version == "1.3" and display_role in {"primary", "supporting"}:
                    missing_unit_lineage = set(source_pointers) - unit_pointer_union
                    if missing_unit_lineage:
                        errors.append(
                            f"{block_id} source_pointers 未分配到任何 semantic unit: "
                            f"{sorted(missing_unit_lineage)}"
                        )
            elif isinstance(block_id, str):
                allowed_content_refs.add(block_id)
                if display_role in {"primary", "supporting"}:
                    required_content_refs.add(block_id)

            if schema_version == "1.3" and page.get("page_type") in {"content", "summary"}:
                body = block.get("body")
                if block.get("type") == "narrative" and isinstance(body, str) and not semantic_units:
                    body_length = len(normalize_text(body))
                    markers = compound_marker_count(body)
                    logic = page.get("visual_intent", {}).get("logic")
                    if body_length > 240 or markers >= 3 or (
                        logic != "single_message" and (body_length > 160 or markers >= 2)
                    ):
                        errors.append(
                            f"{block_id} narrative 含多个原子观点，必须拆成 semantic_units"
                        )
                for item_index, item in enumerate(as_list(block.get("items"))):
                    if isinstance(item, str) and len(normalize_text(item)) > 160 and not semantic_units:
                        errors.append(
                            f"{block_id} items[{item_index}] 过长，必须拆成 semantic_units"
                        )
        if isinstance(composition, dict):
            declared_primary = set(as_list(composition.get("primary_block_ids")))
            if declared_primary and declared_primary != primary_role_ids:
                errors.append(
                    f"{page_id} composition.primary_block_ids 与 block.display_role=primary 不一致"
                )
        if schema_version in {"1.2", "1.3"} and page_blocks and visible_role_count == 0:
            errors.append(f"{page_id} 不能只包含 annotation；至少需要一个 primary 或 supporting block")

        if schema_version == "1.3" and page.get("page_type") in {"content", "summary"}:
            visual = page.get("visual_intent") if isinstance(page.get("visual_intent"), dict) else {}
            structure = visual.get("structure") if isinstance(visual, dict) else None
            if not isinstance(structure, dict):
                errors.append(f"{page_id} 缺少 visual_intent.structure，无法传递页面内部关系")
                continue
            nodes = [node for node in as_list(structure.get("nodes")) if isinstance(node, dict)]
            node_ids: set[str] = set()
            referenced_content: set[str] = set()
            for node in nodes:
                node_id = node.get("node_id")
                if node_id in node_ids:
                    errors.append(f"{page_id} 存在重复 semantic node_id: {node_id}")
                if isinstance(node_id, str):
                    node_ids.add(node_id)
                for content_ref in as_list(node.get("content_refs")):
                    if content_ref not in allowed_content_refs:
                        errors.append(f"{page_id} node {node_id} 引用了不存在的 content_ref: {content_ref}")
                    if content_ref in referenced_content:
                        errors.append(f"{page_id} content_ref 被多个 node 重复使用: {content_ref}")
                    if isinstance(content_ref, str):
                        referenced_content.add(content_ref)
            missing_refs = required_content_refs - referenced_content
            if missing_refs:
                errors.append(
                    f"{page_id} primary/supporting 内容未进入 semantic structure: {sorted(missing_refs)}"
                )
            for group in as_list(structure.get("groups")):
                if not isinstance(group, dict):
                    continue
                unknown_nodes = set(as_list(group.get("node_ids"))) - node_ids
                if unknown_nodes:
                    errors.append(
                        f"{page_id} semantic group {group.get('group_id')} 引用了不存在的 node: "
                        f"{sorted(unknown_nodes)}"
                    )
            links = [link for link in as_list(structure.get("links")) if isinstance(link, dict)]
            for link in links:
                for endpoint in ("from", "to"):
                    if link.get(endpoint) not in node_ids:
                        errors.append(
                            f"{page_id} semantic link {endpoint} 引用了不存在的 node: "
                            f"{link.get(endpoint)}"
                        )
            logic = visual.get("logic")
            if logic in {"parallel", "comparison", "process", "timeline", "hierarchy", "matrix", "portfolio", "decision", "bridge"} and len(nodes) < 2:
                errors.append(f"{page_id} visual_intent.logic={logic} 至少需要 2 个 semantic nodes")
            if logic in {"process", "timeline", "hierarchy", "bridge"} and not links:
                errors.append(f"{page_id} visual_intent.logic={logic} 必须声明 semantic links")
            if logic in {"comparison", "matrix", "portfolio"} and len(as_list(structure.get("groups"))) < 2:
                errors.append(f"{page_id} visual_intent.logic={logic} 至少需要 2 个 semantic groups")
            errors.extend(
                validate_structure_relations(
                    page_id,
                    logic,
                    nodes,
                    [group for group in as_list(structure.get("groups")) if isinstance(group, dict)],
                    links,
                )
            )

    if sequences and sorted(sequences) != list(range(1, len(pages) + 1)):
        errors.append("slide_input sequence 必须从 1 开始连续且不重复")

    if business is None or not isinstance(business, dict):
        errors.append("校验 slide_input.json 时必须同时提供 --business")
        known_assumptions: set[Any] = set()
    else:
        known_assumptions = {
            item.get("id")
            for item in as_list(business.get("assumptions"))
            if isinstance(item, dict)
        }
        if business.get("assumptions") and "assumptions" not in appendix_kinds:
            errors.append("business assumptions 非空，但 slide_input 缺少 assumptions 附录")
        if business.get("data_gaps") and "data_gaps" not in appendix_kinds:
            errors.append("business data_gaps 非空，但 slide_input 缺少 data_gaps 附录")

    if market is None or not isinstance(market, dict):
        errors.append("校验 slide_input.json 时必须同时提供 --market")
        evidence_registry: dict[Any, Any] = {}
    else:
        evidence_registry = {
            item.get("id"): item
            for item in as_list(market.get("evidence_registry"))
            if isinstance(item, dict)
        }
        source_registry = {
            item.get("id"): item
            for item in as_list(market.get("sources"))
            if isinstance(item, dict)
        }

    used_evidence: set[str] = set()
    for _, values in iter_key_values(data, "evidence_ids"):
        if isinstance(values, list):
            for evidence_id in values:
                used_evidence.add(evidence_id)
                if evidence_id not in evidence_registry:
                    errors.append(f"slide_input 中悬空 evidence_id: {evidence_id}")
    for _, values in iter_key_values(data, "assumption_ids"):
        if isinstance(values, list):
            for assumption_id in values:
                if assumption_id not in known_assumptions:
                    errors.append(f"slide_input 中悬空 assumption_id: {assumption_id}")

    if used_evidence and "evidence_mapping" not in appendix_kinds:
        errors.append("slide_input 使用了 evidence_ids，但缺少 evidence_mapping 附录")
    evidence_pages = [
        page
        for page in pages
        if isinstance(page, dict) and page.get("appendix_kind") == "evidence_mapping"
    ]
    evidence_text = flatten_strings(evidence_pages)
    for evidence_id in used_evidence:
        if evidence_id not in evidence_text:
            errors.append(f"evidence_mapping 附录未呈现 {evidence_id}")
        item = evidence_registry.get(evidence_id)
        if isinstance(item, dict):
            for source_id in as_list(item.get("source_ids")):
                if source_id not in evidence_text:
                    errors.append(f"evidence_mapping 附录未呈现 {evidence_id} 对应来源 {source_id}")
                    continue
                source = source_registry.get(source_id)
                if not isinstance(source, dict):
                    errors.append(f"evidence_mapping 引用了不存在的来源 {source_id}")
                    continue
                for field, label in (("title", "标题"), ("publisher", "发布者")):
                    value = source.get(field)
                    if isinstance(value, str) and value and value not in evidence_text:
                        errors.append(f"evidence_mapping 附录未呈现 {source_id} 的{label}: {value}")
    return errors


def validate_coverage(
    data: Any,
    business: Any | None,
    slides: Any | None,
    fidelity_report: dict[str, Any] | None = None,
) -> list[str]:
    errors, warnings = validate_with_schema(data, "slide_coverage.schema.json")
    for warning in warnings:
        print(f"[WARN] {warning}")
    if not isinstance(data, dict):
        return errors + ["slide_coverage.json 顶层必须是对象"]
    if business is None or not isinstance(business, dict):
        return errors + ["校验 slide_coverage.json 时必须同时提供 --business"]
    if slides is None or not isinstance(slides, dict):
        return errors + ["校验 slide_coverage.json 时必须同时提供 --slides"]

    block_pages: dict[str, str] = {}
    blocks: dict[str, dict[str, Any]] = {}
    block_pointers: dict[str, set[str]] = {}
    for page in as_list(slides.get("pages")):
        if not isinstance(page, dict):
            continue
        for block in as_list(page.get("content_blocks")):
            if isinstance(block, dict) and isinstance(block.get("block_id"), str):
                block_pages[block["block_id"]] = page.get("page_type", "")
                blocks[block["block_id"]] = block
                block_pointers[block["block_id"]] = set(as_list(block.get("source_pointers")))

    mappings = as_list(data.get("mappings"))
    by_pointer: dict[str, dict[str, Any]] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        pointer = mapping.get("source_pointer")
        if pointer in by_pointer:
            errors.append(f"slide_coverage source_pointer 重复: {pointer}")
        if isinstance(pointer, str):
            by_pointer[pointer] = mapping
            try:
                resolve_json_pointer(business, pointer)
            except KeyError:
                errors.append(f"slide_coverage source_pointer 不存在: {pointer}")
        placement = mapping.get("placement")
        for block_id in as_list(mapping.get("target_block_ids")):
            if block_id not in block_pages:
                errors.append(f"slide_coverage target_block_id 不存在: {block_id}")
            elif placement == "appendix" and block_pages[block_id] != "appendix":
                errors.append(f"{pointer} 标记 appendix，但 {block_id} 不在附录页")
            elif placement == "main_deck" and block_pages[block_id] == "appendix":
                errors.append(f"{pointer} 标记 main_deck，但 {block_id} 位于附录页")
            elif isinstance(pointer, str) and pointer not in block_pointers.get(block_id, set()):
                errors.append(
                    f"{pointer} 映射到 {block_id}，但该 block.source_pointers 未声明此来源"
                )

    for block_id, pointers in block_pointers.items():
        for pointer in pointers:
            mapping = by_pointer.get(pointer)
            if mapping is None:
                errors.append(f"{block_id} 声明 source_pointer {pointer}，但 coverage 无对应 mapping")
            elif block_id not in as_list(mapping.get("target_block_ids")):
                errors.append(
                    f"{block_id} 声明 source_pointer {pointer}，但 coverage mapping 未回指该 block"
                )

    required_units = business_coverage_units(business)
    importance_rank = {"supporting": 0, "important": 1, "mandatory": 2}
    fidelity_checks: list[dict[str, Any]] = []
    mandatory_total = 0
    mandatory_covered = 0
    for pointer, minimum_importance in required_units.items():
        if minimum_importance == "mandatory":
            mandatory_total += 1
        mapping = by_pointer.get(pointer)
        if mapping is None:
            errors.append(f"slide_coverage 缺少源内容去向: {pointer}")
            fidelity_checks.append(
                {
                    "source_pointer": pointer,
                    "importance": minimum_importance,
                    "status": "missing_mapping",
                    "target_block_ids": [],
                    "missing_atoms": [],
                }
            )
            continue
        actual_importance = mapping.get("importance")
        if importance_rank.get(actual_importance, -1) < importance_rank[minimum_importance]:
            errors.append(
                f"{pointer} importance 至少应为 {minimum_importance}，当前为 {actual_importance}"
            )
        if minimum_importance == "mandatory" and mapping.get("placement") == "omitted":
            errors.append(f"mandatory 源内容不得 omitted: {pointer}")
        expected_placement = required_placement(pointer)
        if expected_placement and mapping.get("placement") != expected_placement:
            errors.append(
                f"{pointer} 必须放入 {expected_placement}，当前为 {mapping.get('placement')}"
            )
        atom_misses: list[str] = []
        if minimum_importance == "mandatory" and mapping.get("placement") != "omitted":
            try:
                source = resolve_json_pointer(business, pointer)
            except KeyError:
                source = None
            target_blocks = [
                blocks[block_id]
                for block_id in as_list(mapping.get("target_block_ids"))
                if block_id in blocks
            ]
            if source is not None:
                atom_misses = missing_atoms(source, target_blocks)
            if atom_misses:
                preview = "；".join(atom_misses[:3])
                errors.append(f"mandatory 源内容未在目标 block 完整呈现: {pointer} -> {preview}")
            else:
                mandatory_covered += 1
        fidelity_checks.append(
            {
                "source_pointer": pointer,
                "importance": minimum_importance,
                "placement": mapping.get("placement"),
                "target_block_ids": as_list(mapping.get("target_block_ids")),
                "status": "pass" if not atom_misses else "content_missing",
                "missing_atoms": atom_misses,
            }
        )
    if fidelity_report is not None:
        fidelity_report.update(
            {
                "schema_version": "1.0",
                "source_file": "business_design.json",
                "target_file": "slide_input.json",
                "required_units": len(required_units),
                "mapped_units": sum(1 for pointer in required_units if pointer in by_pointer),
                "mandatory_units": mandatory_total,
                "mandatory_content_passed": mandatory_covered,
                "mandatory_content_coverage": (
                    round(mandatory_covered / mandatory_total, 4) if mandatory_total else 1.0
                ),
                "checks": fidelity_checks,
            }
        )
    return errors


def validate_state(data: Any) -> list[str]:
    errors, warnings = validate_with_schema(data, "project_state.schema.json")
    for warning in warnings:
        print(f"[WARN] {warning}")
    if isinstance(data, dict) and data.get("schema_version") in {"1.1", "1.2", "1.3"}:
        core_status = data.get("core_status")
        core_artifacts = data.get("core_artifacts") if isinstance(data.get("core_artifacts"), dict) else {}
        stages = data.get("stages") if isinstance(data.get("stages"), dict) else {}
        required_core = ("business_design.json", "business_design.md", "content_quality_report.json")
        if data.get("schema_version") == "1.2":
            required_core = ("business_design.json", "business_design.md", "business_design.html", "business_design.docx", "content_quality_report.json")
        if data.get("schema_version") == "1.3":
            required_core = ("business_design.json", "business_design.md", "business_design.docx", "content_quality_report.json")
        if core_status in {"waiting_for_user", "completed"}:
            missing_core = [
                name for name in required_core
                if not isinstance(core_artifacts.get(name), dict)
                or core_artifacts[name].get("status") != "PASS"
            ]
            if missing_core:
                errors.append(f"core_status={core_status} 但核心产物未全部 PASS: {', '.join(missing_core)}")
            if not isinstance(stages.get("step_05"), dict) or stages["step_05"].get("status") != "passed":
                errors.append(f"core_status={core_status} 但 VDBD Architect step_05 未 PASS")
        if data.get("schema_version") == "1.3":
            if data.get("run_status") == "completed" and core_status != "completed":
                errors.append("run_status=completed 时 core_status 必须为 completed")
            if core_status == "completed" and stages.get("step_07", {}).get("status") != "passed":
                errors.append("core_status=completed 需要 step_07 用户验收通过")
        if core_status == "completed" and data.get("run_status") != "completed":
            errors.append("core_status=completed 时 run_status 必须为 completed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验 business-design 的 schema、引用、评分与跨产物内容覆盖"
    )
    parser.add_argument("--market", type=Path, help="market_insight.json 路径")
    parser.add_argument("--insight-review", type=Path, help="insight_review.json 路径")
    parser.add_argument("--business", type=Path, help="business_design.json 路径")
    parser.add_argument("--slides", type=Path, help="slide_input.json 路径")
    parser.add_argument("--coverage", type=Path, help="slide_coverage.json 路径")
    parser.add_argument("--fidelity-report", type=Path, help="输出 slide_fidelity.json 路径")
    parser.add_argument("--state", type=Path, help="project_state.json 路径")
    args = parser.parse_args()

    if not any((args.market, args.insight_review, args.business, args.slides, args.coverage, args.state)):
        parser.error("至少提供一个待校验产物")
    if args.fidelity_report and not all((args.business, args.slides, args.coverage)):
        parser.error("--fidelity-report 必须同时提供 --business、--slides 和 --coverage")

    try:
        market = load_json(args.market) if args.market else None
        insight_review = load_json(args.insight_review) if args.insight_review else None
        business = load_json(args.business) if args.business else None
        slides = load_json(args.slides) if args.slides else None
        coverage = load_json(args.coverage) if args.coverage else None
        state = load_json(args.state) if args.state else None
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    errors: list[str] = []
    if market is not None:
        errors.extend(validate_market(market))
    if insight_review is not None:
        errors.extend(validate_insight_review(insight_review))
    if business is not None:
        errors.extend(validate_business(business, market))
    if slides is not None:
        errors.extend(validate_slides(slides, business, market))
    fidelity_report: dict[str, Any] = {}
    if coverage is not None:
        errors.extend(validate_coverage(coverage, business, slides, fidelity_report))
    if state is not None:
        errors.extend(validate_state(state))
        if state.get("schema_version") == "1.3" and state.get("core_status") in {"waiting_for_user", "completed"}:
            from design_reliability import delivery
            try:
                project = args.state.parent
                # Validate the artifacts actually being delivered, even for --state alone.
                quality = load_json(project / 'content_quality_report.json')
                paths = quality.get('artifact_paths', {})
                actual_market = load_json(project / paths.get('market_insight.json', 'market_insight.json'))
                actual_business = load_json(project / paths.get('business_design.json', 'business_design.json'))
                actual_review = load_json(project / 'insight_review.json')
                errors.extend(validate_market(actual_market))
                errors.extend(validate_business(actual_business, actual_market))
                errors.extend(validate_insight_review(actual_review))
                errors.extend(delivery(project, state))
            except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
                errors.append(f"交付文件检查失败: {exc}")

    if args.fidelity_report:
        fidelity_report["status"] = "FAIL" if errors else "PASS"
        try:
            args.fidelity_report.write_text(
                json.dumps(fidelity_report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"[INFO] 已输出保真报告: {args.fidelity_report}")
        except OSError as exc:
            errors.append(f"无法写入 fidelity report: {exc}")

    if errors:
        for error in dict.fromkeys(errors):
            print(f"[FAIL] {error}")
        return 1

    print("[PASS] 所有已提供产物通过校验")
    return 0


if __name__ == "__main__":
    sys.exit(main())
