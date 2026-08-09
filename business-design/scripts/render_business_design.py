#!/usr/bin/env python3
"""Render the consulting-semantic model as a transparent Markdown report."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from business_report_model import ReportBlock, ReportDocument, build_report
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from business_report_model import ReportBlock, ReportDocument, build_report  # type: ignore

from business_report_model import CHAPTER_NAMES, FIELD_NAMES  # type: ignore  # public compatibility exports


def _inline(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def _table(block: ReportBlock) -> list[str]:
    lines = [f"### {block.title}", "", "| " + " | ".join(_inline(c) for c in block.columns) + " |",
             "| " + " | ".join("---" for _ in block.columns) + " |"]
    lines.extend("| " + " | ".join(_inline(cell) for cell in row) + " |" for row in block.rows)
    lines.append("")
    return lines


def _render_block(block: ReportBlock, level: int = 3) -> list[str]:
    lines: list[str] = []
    if block.kind == "compact_table":
        return _table(block)
    if block.kind in {"chapter_thesis", "executive_thesis"}:
        value = _inline(block.value) if block.value is not None else ""
        lines.extend([f"> **{_inline(block.title)}**：{value}", ""])
        lines.extend(child for child_block in block.children for child in _render_block(child_block, min(level + 1, 6)))
        return lines
    if block.kind == "note":
        return [f"> {_inline(block.value)}", ""]
    if block.kind in {"source_index", "scalar"}:
        return [f"- **{_inline(block.title)}**：{_inline(block.value)}", ""]
    if block.kind in {"summary_context", "design_conclusions"}:
        lines.extend([f"### {block.title}", ""])
        for child in block.children:
            lines.extend(_render_block(child, min(level + 1, 6)))
        return lines
    if block.kind == "record":
        lines.extend([f"{'#' * min(max(level, 4), 6)} {block.title}", ""])
        for child in block.children:
            lines.extend(_render_block(child, min(level + 1, 6)))
        return lines
    if block.kind in {"record_cards", "fallback_group", "group", "assumption", "data_gap", "decision", "evidence", "implication", "recommendation", "metric", "comparison", "score_matrix", "process", "value_chain", "value_equation", "profit_architecture", "value_capture", "scope_boundary", "control_mechanism", "risk_register"}:
        if block.value is not None and not block.children:
            lines.extend([f"- **{_inline(block.title)}**：{_inline(block.value)}", ""])
            return lines
        lines.extend([f"{'#' * min(max(level, 3), 6)} {block.title}", ""])
        for child in block.children:
            lines.extend(_render_block(child, min(level + 1, 6)))
        if block.kind == "record_cards" and not block.children:
            lines.extend(["- 无", ""])
        return lines
    # Unknown semantic kinds must remain visible rather than silently vanish.
    lines.extend([f"### {block.title}", ""])
    if block.value is not None:
        lines.extend([_inline(block.value), ""])
    for child in block.children:
        lines.extend(_render_block(child, min(level + 1, 6)))
    return lines


def render_document(document: ReportDocument) -> str:
    lines = [f"# {document.company}业务设计报告", "",
             f"<!-- generated-from: {document.source_name}; sha256: {document.source_sha256}; do-not-edit -->", "",
             "> 本文件由 business_design.json 自动生成；正式内容以 JSON 为准，禁止手工补写。", ""]
    for section in document.sections:
        lines.extend([f"## {section.title}", ""])
        for block in section.blocks:
            lines.extend(_render_block(block, 3))
    lines.extend(["## 生成信息", "", f"- **source JSON SHA-256**：{document.source_sha256}", ""])
    return "\n".join(lines).rstrip() + "\n"


def render(data: dict[str, Any], *, source_name: str = "business_design.json", source_sha256: str = "") -> str:
    return render_document(build_report(data, source_name=source_name, source_sha256=source_sha256))


def main() -> int:
    parser = argparse.ArgumentParser(description="从 business_design.json 生成咨询级 Markdown 报告")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()
    output = args.output or args.input.with_name("business_design.md")
    try:
        raw = args.input.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("business_design.json 顶层必须是对象")
        digest = hashlib.sha256(raw).hexdigest()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render(data, source_name=args.input.name, source_sha256=digest), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}")
        return 1
    print(f"[PASS] 已生成咨询级 Markdown：{output}")
    print(f"[INFO] source_sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
