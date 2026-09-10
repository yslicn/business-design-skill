from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseCoreTests(unittest.TestCase):
    def test_all_schemas_are_valid_json(self) -> None:
        for path in sorted((SKILL_DIR / "schemas").glob("*.json")):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict, path.name)

    def test_profit_pattern_origins_use_named_libraries_and_custom_design(self) -> None:
        schema = json.loads((SKILL_DIR / "schemas" / "business_design.schema.json").read_text(encoding="utf-8"))
        origins = schema["properties"]["chapters"]["properties"]["profit_model"]["properties"]["candidate_models"]["items"]["properties"]["pattern_origin"]["enum"]
        # 3.x：按用户口径命名模式库（mercer_slywotzky），不再复制目录内容；
        # 行业观察、自定义与组合设计仍可用；v1 的 published_profit_patterns 已移除。
        self.assertEqual(set(origins), {"mercer_slywotzky", "industry_observed", "custom_designed", "hybrid"})
        self.assertNotIn("published_profit_patterns", origins)

    def test_markdown_renderer_is_deterministic_and_source_hashed(self) -> None:
        renderer = load_module("render_business_design", SCRIPTS / "render_business_design.py")
        data = {
            "company": "Example Co.",
            "industry": "Example industry",
            "strategic_intent": "Choose a defensible growth path",
            "core_pain": "Current economics are weakening",
            "story_line": "Focus on measurable customer value and protected value capture",
            "assumptions": [],
            "chapters": {
                "market_scan": {"key_message": "Value is moving"},
                "customer_selection": {"key_message": "Choose for attractiveness and fit"},
                "value_proposition": {"key_message": "Solve a measurable pain"},
                "profit_model": {"key_message": "Charge against measurable value"},
                "scope_of_activities": {"key_message": "Concentrate activities"},
                "strategic_control": {"key_message": "Protect the economics"},
                "risk_management": {"key_message": "Test assumptions before scaling"},
            },
            "data_gaps": [],
        }
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        first = renderer.render(data, source_name="business_design.json", source_sha256=digest)
        second = renderer.render(data, source_name="business_design.json", source_sha256=digest)
        self.assertEqual(first, second)
        self.assertIn(digest, first)
        self.assertIn("## 4 盈利模式 / 价值获取", first)

    def test_project_state_13_requires_docx_core_without_html(self) -> None:
        schema = json.loads((SKILL_DIR / "schemas" / "project_state.schema.json").read_text(encoding="utf-8"))
        self.assertIn("1.3", schema["properties"]["schema_version"]["enum"])
        validator = load_module("validate_artifacts", SCRIPTS / "validate_artifacts.py")
        stage = {"status": "passed", "reused": False, "revision_count": 0,
                 "artifacts": ["x"], "validation_notes": ["n"]}
        state = {
            "schema_version": "1.3", "project_name": "release-check", "run_mode": "research_provided",
            "run_status": "waiting_for_user", "core_status": "waiting_for_user", "current_step": 7,
            "updated_at": "2026-09-10",
            "stages": {"step_01": stage, "step_02": stage, "step_03": stage, "step_04": stage,
                       "step_05": stage, "step_06": stage, "step_07": stage},
            "core_artifacts": {
                "business_design.json": {"path": "a.json", "status": "PASS"},
                "business_design.md": {"path": "a.md", "status": "PASS"},
                "content_quality_report.json": {"path": "a.json", "status": "PASS"},
                # 故意缺 business_design.docx
            },
        }
        errors = "\n".join(validator.validate_state(state))
        self.assertIn("business_design.docx", errors)
        state["core_artifacts"]["business_design.docx"] = {"path": "a.docx", "status": "PASS"}
        errors = "\n".join(validator.validate_state(state))
        self.assertNotIn("核心产物未全部 PASS", errors)
        self.assertNotIn("business_design.html", errors)


if __name__ == "__main__":
    unittest.main()
