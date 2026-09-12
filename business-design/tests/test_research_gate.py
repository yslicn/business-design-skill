from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit_module = load_module("audit_research_report", ROOT / "scripts" / "audit_research_report.py")
validator = load_module("validate_artifacts_research", ROOT / "scripts" / "validate_artifacts.py")


def sample_review() -> dict:
    return {
        "schema_version": "1.0",
        "status": "PASS",
        "research_report_path": "research_report.html",
        "market_insight_path": "market_insight.json",
        "report_length": {
            "audit_path": "research_report_audit.json",
            "counting_method": audit_module.COUNTING_METHOD,
            "effective_count": 12000,
            "minimum": 10000,
            "maximum": 15000,
            "passed": True,
        },
        "research_coverage": {
            "value_chain_metrics_complete": True,
            "players_and_competition_complete": True,
            "business_models_complete": True,
            "trends_policy_competitors_complete": True,
            "company_specific_inputs_sufficient": True,
            "profit_model_inputs_sufficient": True,
            "data_gaps_disclosed": True,
        },
        "data_integrity": {
            "all_quantitative_claims_traceable": True,
            "verified_claims_supported": True,
            "estimates_labeled_and_reproducible": True,
            "facts_estimates_assumptions_separated": True,
            "suspected_fabrications": [],
            "unsupported_claims": [],
        },
        "business_design_readiness": {
            "market_attractiveness_scoring_ready": True,
            "customer_selection_ready": True,
            "value_proposition_ready": True,
            "profit_model_design_ready": True,
            "limitations_are_actionable": True,
            "summary": "市场洞察足以支持业务设计。",
        },
        "revision_route": "none",
        "issues": [],
        "review_summary": "篇幅、覆盖、真实性与业务设计就绪度均通过。",
    }


class ResearchGateTests(unittest.TestCase):
    def test_v3_sufficient_short_report_keeps_evidence_gate(self):
        review = sample_review()
        review['schema_version'] = '1.1'
        review['sufficiency_rationale'] = '已有材料覆盖客户、付费合同、利润机制和企业能力；剩余缺口已给验证路径。'
        review['report_length']['effective_count'] = 8000
        review['report_length']['passed'] = False
        self.assertEqual(validator.validate_insight_review(review), [])
        review['data_integrity']['verified_claims_supported'] = False
        self.assertTrue(validator.validate_insight_review(review))

    def test_advisory_length_does_not_accept_empty_body(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.md'
            path.write_text('客户访谈显示服务响应时间影响续约，需要结合合同定价和现场工时验证。')
            result = audit_module.audit(path, advisory_length=True)
            self.assertFalse(result['length_passed'])
            self.assertTrue(result['passed'])
            path.write_text('')
            self.assertFalse(audit_module.audit(path, advisory_length=True)['passed'])

    def test_effective_length_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            path.write_text("<html><body>" + "洞" * 10000 + "</body></html>", encoding="utf-8")
            self.assertTrue(audit_module.audit(path)["passed"])
            path.write_text("<html><body>" + "洞" * 9999 + "</body></html>", encoding="utf-8")
            self.assertFalse(audit_module.audit(path)["passed"])
            path.write_text("<html><body>" + "洞" * 15001 + "</body></html>", encoding="utf-8")
            self.assertFalse(audit_module.audit(path)["passed"])

    def test_hidden_html_does_not_pad_length(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            path.write_text(
                "<html><style>" + "假" * 10000 + "</style><body>真实内容</body></html>",
                encoding="utf-8",
            )
            result = audit_module.audit(path)
            self.assertEqual(result["cjk_characters"], 4)
            self.assertFalse(result["passed"])

    def test_reference_list_does_not_pad_body_length(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text("正文\n" + "洞" * 8998 + "\n## 参考文献\n" + "来源" * 1500, encoding="utf-8")
            result = audit_module.audit(path)
            self.assertEqual(result["body_effective_count"], 9000)
            self.assertEqual(result["reference_effective_count"], 3000)
            self.assertFalse(result["length_passed"])
            self.assertFalse(result["passed"])

    def test_unique_body_in_range_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            paragraphs = [f"第{i}段研究结论：" + (chr(0x4e00 + i % 200) * 90) for i in range(120)]
            path.write_text("\n".join(paragraphs), encoding="utf-8")
            result = audit_module.audit(path)
            self.assertTrue(10000 <= result["body_effective_count"] <= 15000)
            self.assertEqual(result["duplicate_paragraph_count"], 0)
            self.assertTrue(result["density_passed"])
            self.assertTrue(result["passed"])

    def test_repeated_paragraphs_cannot_pad_length(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            paragraph = "重复段落：市场增长判断与客户选择依据保持不变。" + "研" * 90
            path.write_text("\n".join([paragraph] * 120), encoding="utf-8")
            result = audit_module.audit(path)
            self.assertTrue(10000 <= result["body_effective_count"] <= 15000)
            self.assertGreater(result["duplicate_paragraph_count"], 100)
            self.assertFalse(result["density_passed"])
            self.assertFalse(result["passed"])

    def test_markdown_html_and_docx_extract_visible_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            md = root / "report.md"
            md.write_text("可见正文", encoding="utf-8")
            self.assertEqual(audit_module.extract_text(md), "可见正文")
            html = root / "report.html"
            html.write_text("<script>隐藏</script><body>可见正文</body>", encoding="utf-8")
            self.assertIn("可见正文", audit_module.extract_text(html))
            self.assertNotIn("隐藏", audit_module.extract_text(html))
            docx = root / "report.docx"
            document = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>可见正文</w:t></w:r></w:p></w:body></w:document>'
            ).encode("utf-8")
            with zipfile.ZipFile(docx, "w") as archive:
                archive.writestr("word/document.xml", document)
            self.assertEqual(audit_module.extract_text(docx), "可见正文")

    def test_valid_insight_review_passes(self):
        self.assertEqual(validator.validate_insight_review(sample_review()), [])

    def test_false_pass_is_rejected(self):
        review = sample_review()
        review["data_integrity"]["all_quantitative_claims_traceable"] = False
        review["data_integrity"]["unsupported_claims"] = ["E09 无法在来源中找到"]
        errors = validator.validate_insight_review(review)
        self.assertTrue(any("all_quantitative_claims_traceable=false" in error for error in errors))
        self.assertTrue(any("unsupported_claims" in error for error in errors))

    def test_revise_routes_back_to_analyst(self):
        review = sample_review()
        review["status"] = "REVISE"
        review["revision_route"] = "supplement_research"
        review["issues"] = [
            {
                "category": "coverage",
                "severity": "blocking",
                "issue": "缺少价值链利润率数据",
                "required_action": "补充各环节同口径利润率及来源",
            }
        ]
        errors = validator.validate_insight_review(review)
        self.assertTrue(any("市场洞察输入质量门未通过" in error for error in errors))

    def test_triangulated_evidence_requires_two_independent_sources(self):
        market = {
            "sources": [
                {"id": "S01", "title": "来源一", "publisher": "机构", "url": "https://example.org/a", "accessed_at": "2026-08-01"}
            ],
            "evidence_registry": [
                {
                    "id": "E01",
                    "statement": "市场增长",
                    "evidence_type": "triangulated",
                    "confidence": "high",
                    "source_ids": ["S01"],
                }
            ],
        }
        errors = validator.validate_market(market)
        self.assertTrue(any("少于两个来源" in error for error in errors))

    def test_duplicate_source_urls_are_rejected(self):
        market = {
            "sources": [
                {"id": "S01", "title": "来源一", "publisher": "机构", "url": "https://example.org/a", "accessed_at": "2026-08-01"},
                {"id": "S02", "title": "来源二", "publisher": "机构", "url": "https://example.org/a/", "accessed_at": "2026-08-01"},
            ],
            "evidence_registry": [],
        }
        errors = validator.validate_market(market)
        self.assertTrue(any("使用重复 URL" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
