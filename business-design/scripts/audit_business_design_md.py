#!/usr/bin/env python3
"""Backward-compatible Markdown audit wrapper over the unified audit engine."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_business_design_outputs import (  # noqa: E402
    REQUIRED_SECTIONS, MARKER_RE, audit_format, load_json, schema_errors,
)

def audit(business_path: Path, markdown_path: Path) -> dict:
    result = audit_format(business_path, markdown_path, "md")
    marker = MARKER_RE.search(markdown_path.read_text(encoding="utf-8"))
    result["schema_version"] = "2.1"
    result["markdown_file"] = markdown_path.name
    result["markdown_sha256"] = result.pop("output_sha256")
    result["generated_marker"] = {
        "present": bool(marker),
        "source_file": marker.group("source").strip() if marker else None,
        "source_sha256": marker.group("sha") if marker else None,
        "matches_current_source": bool(marker and marker.group("sha").lower() == result["source_sha256"]),
    }
    result["data_gap_visibility"] = {"required": len(load_json(business_path).get("data_gaps", [])), "visible": True}
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description="审计 business_design.json 与自动生成 Markdown")
    parser.add_argument("--business", required=True, type=Path); parser.add_argument("--markdown", required=True, type=Path); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try: report = audit(args.business, args.markdown)
    except (OSError, ValueError, json.JSONDecodeError) as exc: print(f"[FAIL] {exc}"); return 1
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[{report['status']}] content quality report -> {args.output}"); return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__": raise SystemExit(main())
