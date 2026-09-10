from pathlib import Path
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location(
    "render_report_exhibits", ROOT / "scripts" / "render_report_exhibits.py")
exhibits_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exhibits_module)


def render_module():
    spec = importlib.util.spec_from_file_location(
        "export_content_report", ROOT / "scripts" / "export_content_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MINI_BUSINESS = {
    "chapters": {"customer_selection": {"segment_evaluation": [
        {"segment": "备件供应", "weighted_score": 4.25,
         "market_attractiveness_contribution": 2.4, "enterprise_fit_contribution": 1.85},
        {"segment": "技术服务与维修", "weighted_score": 4.4,
         "market_attractiveness_contribution": 2.6, "enterprise_fit_contribution": 1.8},
    ]}}
}

MINI_MARKET = {"evidence_registry": [
    {"id": "E01", "statement": "示例事实 11.3%", "evidence_type": "verified",
     "confidence": "high", "source_ids": ["S01"]},
]}


class ExhibitRendererTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        exhibits_module._load_font()

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, exhibits):
        path = self.base / "plan.json"
        path.write_text(json.dumps({"exhibits": exhibits}, ensure_ascii=False))
        return path

    def test_inline_and_auto_types_render_png(self):
        plan = self._plan([
            {"id": "T01", "type": "bar_ranking", "action_title": "对标：A 高于 B",
             "source_refs": ["E01"],
             "data": {"labels": ["A", "B"], "values": [21.0, 11.3], "unit": "%",
                      "evidence": ["E01"]}},
            {"id": "T02", "type": "segment_scores", "action_title": "环节评分排序",
             "source_refs": [], "data": {}},
            {"id": "T03", "type": "contribution_stack", "action_title": "贡献构成",
             "source_refs": [], "data": {}},
            {"id": "T04", "type": "risk_matrix", "action_title": "风险分级",
             "source_refs": [],
             "data": {"risks": [{"label": "收款", "likelihood": 4, "impact": 5, "tier": "生死"}]}},
        ])
        out = self.base / "exhibits"
        manifest = exhibits_module.render_plan(plan, out, MINI_BUSINESS, MINI_MARKET)
        self.assertEqual(manifest["exhibit_count"], 4)
        for item in manifest["exhibits"]:
            png = out / f"{item['id']}.png"
            self.assertTrue(png.is_file() and png.stat().st_size > 5000, item["id"])
        self.assertTrue((out / "exhibits_manifest.json").is_file())
        # 自动类型按分数排序：技术服务与维修 4.40 应排第一
        self.assertEqual(manifest["exhibits"][1]["traced_source"],
                         "business_design.json:chapters.customer_selection.segment_evaluation")

    def test_dangling_source_ref_rejected(self):
        plan = self._plan([
            {"id": "T01", "type": "bar_ranking", "action_title": "标题",
             "source_refs": ["E99"],
             "data": {"labels": ["A"], "values": [1], "evidence": []}},
        ])
        with self.assertRaisesRegex(ValueError, "E99"):
            exhibits_module.render_plan(plan, self.base / "ex1", MINI_BUSINESS, MINI_MARKET)

    def test_unknown_type_and_missing_title_rejected(self):
        plan = self._plan([
            {"id": "T01", "type": "pie_3d", "action_title": "标题", "data": {}},
        ])
        with self.assertRaisesRegex(ValueError, "不支持的展项类型"):
            exhibits_module.render_plan(plan, self.base / "ex2", None, None)
        plan = self._plan([
            {"id": "T01", "type": "funnel", "data": {"layers": [{"label": "A"}]}},
        ])
        with self.assertRaisesRegex(ValueError, "action_title"):
            exhibits_module.render_plan(plan, self.base / "ex3", None, None)

    def test_auto_type_requires_business_json(self):
        plan = self._plan([
            {"id": "T01", "type": "segment_scores", "action_title": "标题", "data": {}},
        ])
        with self.assertRaisesRegex(ValueError, "business_design.json"):
            exhibits_module.render_plan(plan, self.base / "ex4", None, MINI_MARKET)

    @unittest.skipUnless(shutil.which("pandoc"), "pandoc required")
    def test_export_embeds_exhibits_and_passes_inventory(self):
        plan = self._plan([
            {"id": "T01", "type": "bar_ranking", "action_title": "对标：A 高于 B",
             "source_refs": ["E01"],
             "data": {"labels": ["A", "B"], "values": [21.0, 11.3], "unit": "%",
                      "evidence": ["E01"]}},
        ])
        exhibits_module.render_plan(plan, self.base / "exhibits", MINI_BUSINESS, MINI_MARKET)
        md = self.base / "business_design.md"
        md.write_text(
            "# 测试报告\n\n核心判断：A 显著高于 B [E01]。\n\n"
            "![T01 对标：A 高于 B](exhibits/T01.png)\n")
        module = render_module()
        manifest = module.export(md, self.base / "report", "PingFang SC",
                                 {"title": "测试", "company": "示例", "date": "2026-09"})
        self.assertEqual(manifest["conversion_status"], "PASS")
        self.assertEqual(len(manifest["exhibits"]), 1)
        from docx import Document
        document = Document(self.base / "report" / "business_design.docx")
        self.assertEqual(len(document.inline_shapes), 1)

    @unittest.skipUnless(shutil.which("pandoc"), "pandoc required")
    def test_export_rejects_missing_exhibit_image(self):
        md = self.base / "broken.md"
        md.write_text("# 测试\n\n![不存在](exhibits/none.png)\n")
        module = render_module()
        with self.assertRaises(ValueError):
            module.export(md, self.base / "report2", "PingFang SC")


if __name__ == "__main__":
    unittest.main()
