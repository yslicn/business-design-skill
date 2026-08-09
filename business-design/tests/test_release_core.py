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

    def test_profit_pattern_origins_support_original_and_legacy_inputs(self) -> None:
        schema = json.loads((SKILL_DIR / "schemas" / "business_design.schema.json").read_text(encoding="utf-8"))
        origins = schema["properties"]["chapters"]["properties"]["profit_model"]["properties"]["candidate_models"]["items"]["properties"]["pattern_origin"]["enum"]
        self.assertIn("published_profit_patterns", origins)
        self.assertIn("industry_observed", origins)
        self.assertIn("custom_designed", origins)
        self.assertIn("mercer_slywotzky", origins)  # read compatibility; not the new default

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

    def test_project_state_requires_only_content_first_core(self) -> None:
        schema = json.loads((SKILL_DIR / "schemas" / "project_state.schema.json").read_text(encoding="utf-8"))
        required = schema["properties"]["core_artifacts"]["required"]
        self.assertEqual(
            required,
            ["business_design.json", "business_design.md", "content_quality_report.json"],
        )
        self.assertNotIn("business_design.html", required)
        self.assertNotIn("business_design.docx", required)


if __name__ == "__main__":
    unittest.main()
