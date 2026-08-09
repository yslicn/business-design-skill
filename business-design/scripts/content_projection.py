#!/usr/bin/env python3
"""Deterministic projections of content that may be visible in a deck.

Business-design uses this module for both inventory generation and fidelity
checks.  Traceability/control metadata is deliberately kept out of visible
content so IDs cannot create a false fidelity pass.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


# These keys identify lineage, schema/control state, or internal enums.  They
# may be audited separately, but must not count as visible business content.
METADATA_KEYS = {
    "id",
    "unit_id",
    "block_id",
    "node_id",
    "group_id",
    "source_pointer",
    "source_pointers",
    "source_file",
    "target_file",
    "schema_version",
    "source_business_schema_version",
    "evidence_ids",
    "assumption_ids",
    "display_role",
    "role",
    "importance",
    "placement",
    "required_placement",
    "source_type",
    "pattern_origin",
    "fit",
    "status",
    "type",
    "evidence_type",
    "confidence",
    "higher_is_better",
    "library_version",
}

INTERNAL_ENUM_VALUES = {
    "mandatory",
    "important",
    "supporting",
    "primary",
    "annotation",
    "claim",
    "evidence",
    "implication",
    "condition",
    "decision",
    "metric",
    "directional",
    "not_available",
    "high",
    "medium",
    "low",
    "rejected",
    "profit_model",
    "customer_selection",
    "assumptions",
    "data_gaps",
    "main_deck",
    "appendix",
    "omitted",
}

QUALIFIER_TERMS = (
    "必须",
    "不得",
    "仅",
    "至少",
    "最高",
    "最低",
    "优先",
    "不等于",
    "假设",
    "方向性",
    "estimated",
    "unknown",
    "verified",
    "triangulated",
)

NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:\d+(?:\.\d+)?|\.\d+)(?:\s*[%％]|\s*[万亿亿元吨家年倍×xX]|\s*[A-Za-z]{1,8})?"
)
NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?|\.\d+)(\s*[%％]|\s*[万亿亿元吨家年倍×xX]|\s*[A-Za-z]{1,8})?"
)


def normalize_text(value: Any) -> str:
    """Normalize whitespace/full-width punctuation for deterministic matching."""

    text = str(value)
    translations = str.maketrans(
        {
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "＋": "+",
            "％": "%",
        }
    )
    return re.sub(r"\s+", "", text.translate(translations)).lower()


def _walk_business(value: Any, *, parent_key: str | None = None) -> list[str]:
    atoms: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in METADATA_KEYS or key.endswith("_id") or key.endswith("_ids"):
                continue
            atoms.extend(_walk_business(child, parent_key=key))
    elif isinstance(value, list):
        for child in value:
            atoms.extend(_walk_business(child, parent_key=parent_key))
    elif isinstance(value, (str, int, float, bool)):
        text = str(value).strip()
        if text and normalize_text(text) not in INTERNAL_ENUM_VALUES:
            atoms.append(text)
    return atoms


def business_visible_atoms(value: Any) -> list[str]:
    """Return visible source atoms, excluding control/lineage metadata."""

    return _walk_business(value)


def business_lineage_ids(value: Any, key: str) -> list[str]:
    """Collect evidence/assumption IDs in source order without duplicates."""

    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for child_key, child in node.items():
                if child_key == key and isinstance(child, list):
                    for item in child:
                        if isinstance(item, str) and item not in found:
                            found.append(item)
                else:
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return found


def protected_numbers(atoms: list[str]) -> list[str]:
    """Extract numeric atoms in stable first-seen order."""

    result: list[str] = []
    for atom in atoms:
        for match in NUMBER_PATTERN.findall(atom):
            normalized = normalize_text(match)
            if normalized and normalized not in result:
                result.append(normalized)
    return result


def protected_qualifiers(atoms: list[str]) -> list[str]:
    """Extract conclusion-strength/epistemic qualifiers in stable order."""

    result: list[str] = []
    for atom in atoms:
        normalized = normalize_text(atom)
        for term in QUALIFIER_TERMS:
            if normalize_text(term) in normalized and term not in result:
                result.append(term)
    return result


def numeric_tokens(value: Any) -> list[tuple[float, str]]:
    """Return numeric values with a unit-aware canonical representation."""

    tokens: list[tuple[float, str]] = []
    for match in NUMERIC_TOKEN_PATTERN.finditer(str(value)):
        number = float(match.group(1))
        suffix = normalize_text(match.group(2) or "")
        if suffix == "%":
            # A ratio and a percentage are equivalent only under this explicit
            # conversion; 0.55% therefore remains 0.0055, not 0.55.
            tokens.append((round(number / 100, 10), "ratio"))
        elif not suffix and 0 <= number <= 1:
            tokens.append((round(number, 10), "ratio"))
        else:
            tokens.append((round(number, 10), suffix or "number"))
    return tokens


def qualifier_tokens(value: Any) -> list[str]:
    normalized = normalize_text(value)
    return [term for term in QUALIFIER_TERMS if normalize_text(term) in normalized]


def _append_scalar(out: list[str], value: Any) -> None:
    if isinstance(value, (str, int, float, bool)) and str(value).strip():
        out.append(str(value))


def slide_visible_projection(page: dict[str, Any]) -> list[str]:
    """Project only fields that can be rendered as visible slide content."""

    out: list[str] = []
    for key in ("action_title", "key_message", "footnotes"):
        value = page.get(key)
        if isinstance(value, list):
            for item in value:
                _append_scalar(out, item)
        else:
            _append_scalar(out, value)

    for block in page.get("content_blocks", []):
        if not isinstance(block, dict):
            continue
        _append_scalar(out, block.get("heading"))
        _append_scalar(out, block.get("body"))
        for item in block.get("items", []):
            _append_scalar(out, item)
        for unit in block.get("semantic_units", []):
            if isinstance(unit, dict):
                _append_scalar(out, unit.get("headline"))
                _append_scalar(out, unit.get("detail"))
        table = block.get("table")
        if isinstance(table, dict):
            for column in table.get("columns", []):
                _append_scalar(out, column)
            for row in table.get("rows", []):
                if isinstance(row, list):
                    for cell in row:
                        _append_scalar(out, cell)
        chart = block.get("chart")
        if isinstance(chart, dict):
            for category in chart.get("categories", []):
                _append_scalar(out, category)
            for series in chart.get("series", []):
                if isinstance(series, dict):
                    _append_scalar(out, series.get("name"))
                    for value in series.get("values", []):
                        _append_scalar(out, value)
            _append_scalar(out, chart.get("unit"))
        for kpi in block.get("kpis", []):
            if isinstance(kpi, dict):
                for key in ("label", "value", "interpretation"):
                    _append_scalar(out, kpi.get(key))
    return out


def slide_blocks_visible_projection(blocks: list[dict[str, Any]]) -> list[str]:
    """Project a list of blocks without treating IDs/roles as visible text."""

    return slide_visible_projection({"content_blocks": blocks})


def slide_structure_labels(structure: dict[str, Any]) -> list[str]:
    """Return labels for relation checks only; not part of fidelity coverage."""

    labels: list[str] = []
    for node in structure.get("nodes", []):
        if isinstance(node, dict):
            _append_scalar(labels, node.get("label"))
    for group in structure.get("groups", []):
        if isinstance(group, dict):
            _append_scalar(labels, group.get("label"))
    for link in structure.get("links", []):
        if isinstance(link, dict):
            _append_scalar(labels, link.get("label"))
    return labels
