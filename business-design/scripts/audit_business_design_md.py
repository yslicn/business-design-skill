#!/usr/bin/env python3
"""Audit the deterministic Markdown projection of business_design.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from content_projection import (
        business_lineage_ids,
        business_visible_atoms,
        normalize_text,
        numeric_tokens,
        protected_qualifiers,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from content_projection import (  # type: ignore[no-redef]
        business_lineage_ids,
        business_visible_atoms,
        normalize_text,
        numeric_tokens,
        protected_qualifiers,
    )

MARKER_RE = re.compile(
    r"generated-from:\s*(?P<source>[^;]+);\s*sha256:\s*(?P<sha>[0-9a-fA-F]{64})",
    re.I,
)
EVIDENCE_RE = re.compile(r"\bE\d+\b")
ASSUMPTION_RE = re.compile(r"\bA\d+\b")
REQUIRED_SECTIONS = [
    "## 执行摘要",
    "## 研究范围与证据口径",
    "## 1 市场扫描",
    "## 2 客户选择",
    "## 3 价值主张",
    "## 4 盈利模式 / 价值获取",
    "## 5 活动范围",
    "## 6 战略控制",
    "## 7 风险管理",
    "## 关键假设与验证计划",
    "## 数据缺口",
    "## 证据索引",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON top level must be an object: {path}")
    return value


def schema_errors(data: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft7Validator
    except ImportError:
        return ["jsonschema is not installed"]
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "business_design.schema.json"
    schema = load_json(schema_path)
    return [
        f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(Draft7Validator(schema).iter_errors(data), key=lambda item: list(item.path))
    ]


def id_coverage(data: dict[str, Any], text: str, key: str, pattern: re.Pattern[str]) -> dict[str, Any]:
    required = business_lineage_ids(data, key)
    found = set(pattern.findall(text))
    missing = [item for item in required if item not in found]
    return {
        "required": required,
        "missing": missing,
        "coverage": round((len(required) - len(missing)) / len(required), 4) if required else 1.0,
    }


def audit(business_path: Path, markdown_path: Path) -> dict[str, Any]:
    raw = business_path.read_bytes()
    source_sha = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("business_design.json top level must be an object")
    text = markdown_path.read_text(encoding="utf-8")
    marker = MARKER_RE.search(text)
    normalized = normalize_text(text)

    atoms = [atom for atom in business_visible_atoms(data) if normalize_text(atom)]
    required_counts = Counter(normalize_text(atom) for atom in atoms)
    missing_atoms = [
        atom for atom in atoms if normalized.count(normalize_text(atom)) < required_counts[normalize_text(atom)]
    ]

    source_numbers = list(dict.fromkeys(token for atom in atoms for token in numeric_tokens(atom)))
    target_numbers = Counter(numeric_tokens(text))
    missing_numbers: list[str] = []
    for number, unit in source_numbers:
        if target_numbers[(number, unit)]:
            target_numbers[(number, unit)] -= 1
        else:
            missing_numbers.append(f"{number:g}{unit}")

    qualifiers = protected_qualifiers(atoms)
    missing_qualifiers = [item for item in qualifiers if normalize_text(item) not in normalized]
    evidence = id_coverage(data, text, "evidence_ids", EVIDENCE_RE)
    assumptions = id_coverage(data, text, "assumption_ids", ASSUMPTION_RE)
    sections_missing = [section for section in REQUIRED_SECTIONS if section not in text]
    schema = schema_errors(data)
    issues: list[str] = []
    if schema:
        issues.append("business_design.json schema validation failed")
    if not marker or marker.group("sha").lower() != source_sha:
        issues.append("Markdown source hash is missing or does not match")
    if sections_missing:
        issues.append("required Markdown sections are missing")
    if missing_atoms:
        issues.append(f"{len(missing_atoms)} visible JSON values are missing")
    if missing_numbers:
        issues.append(f"{len(missing_numbers)} protected numeric tokens are missing")
    if missing_qualifiers:
        issues.append("protected qualifiers are missing")
    if evidence["missing"]:
        issues.append("evidence IDs are missing")
    if assumptions["missing"]:
        issues.append("assumption IDs are missing")

    return {
        "schema_version": "1.0",
        "status": "PASS" if not issues else "FAIL",
        "source_file": business_path.name,
        "source_sha256": source_sha,
        "markdown_file": markdown_path.name,
        "markdown_sha256": hashlib.sha256(markdown_path.read_bytes()).hexdigest(),
        "source_hash": {
            "embedded": marker.group("sha").lower() if marker else None,
            "matches": bool(marker and marker.group("sha").lower() == source_sha),
        },
        "schema_validation": {"status": "PASS" if not schema else "FAIL", "errors": schema},
        "required_sections": {"missing": sections_missing, "coverage": round((len(REQUIRED_SECTIONS) - len(sections_missing)) / len(REQUIRED_SECTIONS), 4)},
        "mandatory_field_coverage": {"total": len(atoms), "missing": missing_atoms[:100], "coverage": round((len(atoms) - len(missing_atoms)) / len(atoms), 4) if atoms else 1.0},
        "protected_numbers": {"required": len(source_numbers), "missing": missing_numbers, "coverage": round((len(source_numbers) - len(missing_numbers)) / len(source_numbers), 4) if source_numbers else 1.0},
        "qualifier_coverage": {"required": qualifiers, "missing": missing_qualifiers, "coverage": round((len(qualifiers) - len(missing_qualifiers)) / len(qualifiers), 4) if qualifiers else 1.0},
        "evidence_id_coverage": evidence,
        "assumption_id_coverage": assumptions,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit business_design.json and generated Markdown")
    parser.add_argument("--business", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.business, args.markdown)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}")
        return 1
    print(f"[{report['status']}] content quality report -> {args.output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
