#!/usr/bin/env python3
"""Validate content-first business-design artifacts and cross-file references."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_DIR = SKILL_DIR / "schemas"
MARKET_DIMENSIONS = ("profit_pool_size", "growth_and_value_migration", "competitive_attractiveness")
ENTERPRISE_DIMENSIONS = ("capability_fit", "business_synergy", "feasibility_and_risk")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def iter_key_values(value: Any, key: str) -> Iterable[Any]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == key:
                yield child
            yield from iter_key_values(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from iter_key_values(child, key)


def duplicate_ids(items: list[Any], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        item_id = item["id"]
        if item_id in seen:
            errors.append(f"{label} has duplicate ID: {item_id}")
        seen.add(item_id)
    return errors


def validate_with_schema(data: Any, schema_name: str) -> list[str]:
    try:
        from jsonschema import Draft7Validator
    except ImportError:
        return ["jsonschema is not installed"]
    schema = load_json(SCHEMA_DIR / schema_name)
    return [
        f"schema {'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(Draft7Validator(schema).iter_errors(data), key=lambda item: list(item.path))
    ]


def validate_market(data: Any) -> list[str]:
    errors = validate_with_schema(data, "market_insight.schema.json")
    if not isinstance(data, dict):
        return errors + ["market_insight.json top level must be an object"]
    sources = as_list(data.get("sources"))
    evidence = as_list(data.get("evidence_registry"))
    errors.extend(duplicate_ids(sources, "sources"))
    errors.extend(duplicate_ids(evidence, "evidence_registry"))
    source_ids = {item.get("id") for item in sources if isinstance(item, dict)}
    evidence_ids = {item.get("id") for item in evidence if isinstance(item, dict)}
    source_urls: dict[Any, str] = {}
    seen_urls: dict[str, Any] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = source.get("id")
        url = source.get("url")
        if isinstance(url, str):
            normalized = url.strip().lower().rstrip("/")
            source_urls[source_id] = normalized
            if not re.match(r"^https?://", url.strip(), re.I):
                errors.append(f"source {source_id} URL is not http(s): {url}")
            if normalized in seen_urls:
                errors.append(f"sources {source_id} and {seen_urls[normalized]} reuse one URL")
            seen_urls[normalized] = source_id
    for values in iter_key_values(data, "source_ids"):
        for source_id in as_list(values):
            if source_id not in source_ids:
                errors.append(f"unresolved source_id: {source_id}")
    for values in iter_key_values(data, "evidence_ids"):
        for evidence_id in as_list(values):
            if evidence_id not in evidence_ids:
                errors.append(f"unresolved evidence_id: {evidence_id}")
    for item in evidence:
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("id", "<unknown>")
        linked = as_list(item.get("source_ids"))
        if item.get("evidence_type") == "triangulated":
            distinct = {source_urls[source_id] for source_id in linked if source_id in source_urls}
            if len(linked) < 2 or len(distinct) < 2:
                errors.append(f"{evidence_id} is triangulated without two independent source URLs")
        if item.get("evidence_type") == "estimated" and not str(item.get("calculation_or_basis", "")).strip():
            errors.append(f"{evidence_id} is estimated without calculation_or_basis")
    return errors


def validate_insight_review(data: Any) -> list[str]:
    errors = validate_with_schema(data, "insight_review.schema.json")
    if not isinstance(data, dict):
        return errors + ["insight_review.json top level must be an object"]
    length = data.get("report_length") if isinstance(data.get("report_length"), dict) else {}
    count = length.get("effective_count")
    in_range = isinstance(count, int) and 10_000 <= count <= 15_000
    if length.get("passed") != in_range:
        errors.append("report_length.passed disagrees with the 10,000–15,000 effective-length gate")
    if data.get("status") != "PASS":
        errors.append(f"market-insight gate is not PASS: {data.get('status')} / {data.get('revision_route')}")
        return errors
    for group_name in ("research_coverage", "data_integrity", "business_design_readiness"):
        group = data.get(group_name)
        if isinstance(group, dict):
            for field, value in group.items():
                if isinstance(value, bool) and not value:
                    errors.append(f"status=PASS but {group_name}.{field}=false")
    integrity = data.get("data_integrity") if isinstance(data.get("data_integrity"), dict) else {}
    if as_list(integrity.get("suspected_fabrications")):
        errors.append("status=PASS but suspected_fabrications is not empty")
    if as_list(integrity.get("unsupported_claims")):
        errors.append("status=PASS but unsupported_claims is not empty")
    if not in_range:
        errors.append("status=PASS but research length is outside the hard gate")
    for issue in as_list(data.get("issues")):
        if isinstance(issue, dict) and issue.get("severity") in {"blocking", "major"}:
            errors.append("status=PASS but a blocking/major issue remains")
    return errors


def validate_business(data: Any, market: Any | None) -> list[str]:
    errors = validate_with_schema(data, "business_design.schema.json")
    if not isinstance(data, dict):
        return errors + ["business_design.json top level must be an object"]
    assumptions = as_list(data.get("assumptions"))
    errors.extend(duplicate_ids(assumptions, "assumptions"))
    assumption_ids = {item.get("id") for item in assumptions if isinstance(item, dict)}
    for values in iter_key_values(data, "assumption_ids"):
        for assumption_id in as_list(values):
            if assumption_id not in assumption_ids:
                errors.append(f"unresolved assumption_id: {assumption_id}")
    if not isinstance(market, dict):
        errors.append("business validation requires --market")
    else:
        known_evidence = {item.get("id") for item in as_list(market.get("evidence_registry")) if isinstance(item, dict)}
        for values in iter_key_values(data, "evidence_ids"):
            for evidence_id in as_list(values):
                if evidence_id not in known_evidence:
                    errors.append(f"unresolved business evidence_id: {evidence_id}")

    chapters = data.get("chapters") if isinstance(data.get("chapters"), dict) else {}
    selection = chapters.get("customer_selection") if isinstance(chapters.get("customer_selection"), dict) else {}
    method = selection.get("selection_method") if isinstance(selection.get("selection_method"), dict) else {}
    weights = method.get("dimension_weights") if isinstance(method.get("dimension_weights"), dict) else {}
    if weights:
        total = sum(value for value in weights.values() if isinstance(value, (int, float)))
        market_weight = method.get("market_attractiveness_weight")
        fit_weight = method.get("enterprise_fit_weight")
        if abs(total - 1.0) > 0.001:
            errors.append(f"dimension weights sum to {total:.4f}, not 1")
        if not isinstance(market_weight, (int, float)) or not isinstance(fit_weight, (int, float)):
            errors.append("selection method lacks market-attractiveness or enterprise-fit weight")
        else:
            if abs(market_weight + fit_weight - 1.0) > 0.001:
                errors.append("market-attractiveness + enterprise-fit weights must equal 1")
            if abs(sum(weights.get(name, 0) for name in MARKET_DIMENSIONS) - market_weight) > 0.001:
                errors.append("market-attractiveness dimension weights do not match their group weight")
            if abs(sum(weights.get(name, 0) for name in ENTERPRISE_DIMENSIONS) - fit_weight) > 0.001:
                errors.append("enterprise-fit dimension weights do not match their group weight")
    for evaluation in as_list(selection.get("segment_evaluation")):
        if not isinstance(evaluation, dict) or not weights:
            continue
        scores = evaluation.get("scores") if isinstance(evaluation.get("scores"), dict) else {}
        if not all(name in scores for name in (*MARKET_DIMENSIONS, *ENTERPRISE_DIMENSIONS)):
            continue
        expected_market = round(sum(scores[name] * weights[name] for name in MARKET_DIMENSIONS), 2)
        expected_fit = round(sum(scores[name] * weights[name] for name in ENTERPRISE_DIMENSIONS), 2)
        expected_total = round(expected_market + expected_fit, 2)
        label = evaluation.get("segment", "<unknown>")
        for field, expected in (
            ("market_attractiveness_contribution", expected_market),
            ("enterprise_fit_contribution", expected_fit),
            ("weighted_score", expected_total),
        ):
            actual = evaluation.get(field)
            if not isinstance(actual, (int, float)) or abs(actual - expected) > 0.01:
                errors.append(f"{label} {field} should be {expected}, got {actual}")

    profit = chapters.get("profit_model") if isinstance(chapters.get("profit_model"), dict) else {}
    candidates = as_list(profit.get("candidate_models"))
    equations = as_list(profit.get("customer_value_equations"))
    mechanisms = as_list(profit.get("value_capture_mechanisms"))
    errors.extend(duplicate_ids(candidates, "candidate_models"))
    errors.extend(duplicate_ids(equations, "customer_value_equations"))
    errors.extend(duplicate_ids(mechanisms, "value_capture_mechanisms"))
    candidate_ids = {item.get("id") for item in candidates if isinstance(item, dict)}
    equation_ids = {item.get("id") for item in equations if isinstance(item, dict)}
    screening = profit.get("pattern_screening") if isinstance(profit.get("pattern_screening"), dict) else {}
    shortlist = set(as_list(screening.get("shortlisted_model_ids")))
    if shortlist != candidate_ids:
        errors.append("shortlisted_model_ids must exactly match candidate model IDs")
    selected = profit.get("selected_architecture") if isinstance(profit.get("selected_architecture"), dict) else {}
    selected_ids = [selected.get("primary_model_id"), *as_list(selected.get("supporting_model_ids"))]
    if len(selected_ids) != len(set(selected_ids)):
        errors.append("primary and supporting model IDs must be unique")
    for model_id in selected_ids:
        if model_id not in candidate_ids:
            errors.append(f"selected architecture references unknown candidate: {model_id}")
    linked_models: set[Any] = set()
    linked_equations: set[Any] = set()
    for mechanism in mechanisms:
        if not isinstance(mechanism, dict):
            continue
        for model_id in as_list(mechanism.get("linked_model_ids")):
            linked_models.add(model_id)
            if model_id not in selected_ids:
                errors.append(f"mechanism links an unselected profit model: {model_id}")
        for equation_id in as_list(mechanism.get("linked_value_equation_ids")):
            linked_equations.add(equation_id)
            if equation_id not in equation_ids:
                errors.append(f"mechanism links an unknown value equation: {equation_id}")
    for model_id in selected_ids:
        if model_id not in linked_models:
            errors.append(f"selected profit model has no value-capture mechanism: {model_id}")
    for equation_id in equation_ids:
        if equation_id not in linked_equations:
            errors.append(f"customer value equation has no value-capture mechanism: {equation_id}")
    return errors


def validate_state(data: Any) -> list[str]:
    errors = validate_with_schema(data, "project_state.schema.json")
    if not isinstance(data, dict):
        return errors
    if data.get("core_status") in {"waiting_for_user", "completed"}:
        artifacts = data.get("core_artifacts") if isinstance(data.get("core_artifacts"), dict) else {}
        required = ("business_design.json", "business_design.md", "content_quality_report.json")
        missing = [name for name in required if not isinstance(artifacts.get(name), dict) or artifacts[name].get("status") != "PASS"]
        if missing:
            errors.append("completed/waiting core has non-PASS artifacts: " + ", ".join(missing))
        stages = data.get("stages") if isinstance(data.get("stages"), dict) else {}
        if not isinstance(stages.get("step_05"), dict) or stages["step_05"].get("status") != "passed":
            errors.append("completed/waiting core requires an independent step_05 PASS")
    if data.get("core_status") == "completed" and data.get("run_status") != "completed":
        errors.append("core_status=completed requires run_status=completed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate content-first business-design artifacts")
    parser.add_argument("--market", type=Path)
    parser.add_argument("--insight-review", type=Path)
    parser.add_argument("--business", type=Path)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    if not any((args.market, args.insight_review, args.business, args.state)):
        parser.error("provide at least one artifact")
    try:
        market = load_json(args.market) if args.market else None
        errors: list[str] = []
        if market is not None:
            errors.extend(validate_market(market))
        if args.insight_review:
            errors.extend(validate_insight_review(load_json(args.insight_review)))
        if args.business:
            errors.extend(validate_business(load_json(args.business), market))
        if args.state:
            errors.extend(validate_state(load_json(args.state)))
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1
    print("[PASS] all provided content-first artifacts are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
