from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_content_report import export
from validate_artifacts import validate_state


class ContentReportTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('pandoc'), 'pandoc required')
    def test_export_preserves_manuscript_tables_links_and_qualifiers(self):
        from docx import Document
        source_text = '''# 业务设计：先验证客户价值，再扩大投入

## 盈利模式

建议先测试**按设备收费**，而非假定所有客户愿意支付溢价。[E01] 这一判断为方向性建议，未知成本不能写成 0；需验证现金转换周期。[^a]

| 场景 | 单价 | 条件 |
|---|---:|---|
| 基准 | 120 元/台 | 假设续约率 80% |
| 压力 | 100 元/台 | 尚未验证 |

收入 = 设备数量 × 服务单价。选择是否成立，取决于贡献利润和回款，而不仅是收入增长。

- 第一阶段：验证付费意愿。
- 第二阶段：复核服务工时。

## 来源与假设

[E01] [示例来源](https://example.org/report)，仅为转换测试。

[^a]: 假设 A01 尚待验证，不能作为已核实事实。
'''
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'source.md'
            source.write_text(source_text)
            output = base / 'report'
            result = export(source, output, 'PingFang SC')
            self.assertEqual((output / 'business_design.md').read_bytes(), source.read_bytes())
            self.assertEqual(set(p.name for p in output.iterdir()),
                             {'business_design.md', 'business_design.docx', 'report_manifest.json'})
            doc = Document(output / 'business_design.docx')
            self.assertEqual(len(doc.tables[0].rows), 3)
            self.assertIn('https://example.org/report', [r.target_ref for r in doc.part.rels.values()])
            self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest(), doc.core_properties.subject)
            self.assertEqual(result['content_review'], 'PENDING')
            self.assertEqual(result['docx_readability'], 'PENDING')
            before = (output / 'business_design.docx').read_bytes()
            with self.assertRaises(ValueError):
                export(source, output, 'PingFang SC')
            self.assertEqual(before, (output / 'business_design.docx').read_bytes())

    @unittest.skipUnless(shutil.which('pandoc'), 'pandoc required')
    def test_failed_conversion_publishes_no_partial_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'source.md'
            source.write_text('# 测试\n\n不可遗漏的原文。')
            with patch('export_content_report.polish_docx', side_effect=ValueError('failure')):
                with self.assertRaises(ValueError):
                    export(source, base / 'report', 'PingFang SC')
            self.assertFalse((base / 'report').exists())

    def test_v3_completion_requires_docx_but_not_html(self):
        state = {
            'schema_version': '1.3', 'project_name': 'sample', 'run_mode': 'full',
            'run_status': 'completed', 'core_status': 'completed', 'current_step': 7,
            'updated_at': '2026-09-10', 'optional_exports': [],
            'stages': {f'step_{i:02}': {'status': 'passed', 'reused': False,
                       'revision_count': 0, 'artifacts': [], 'validation_notes': []}
                       for i in range(1, 8)},
            'core_artifacts': {name: {'path': name, 'status': 'PASS'} for name in
                ('business_design.json', 'business_design.md', 'business_design.docx', 'content_quality_report.json')}
        }
        self.assertEqual(validate_state(state), [])
        state['core_artifacts']['business_design.docx']['status'] = 'PENDING'
        self.assertTrue(validate_state(state))
        state['core_artifacts']['business_design.docx']['status'] = 'PASS'
        state['core_status'] = 'in_progress'
        self.assertTrue(validate_state(state))
        state['core_status'] = 'completed'
        state['stages']['step_07']['status'] = 'pending'
        self.assertTrue(validate_state(state))
        state['stages']['step_07']['status'] = 'passed'
        state['schema_version'] = '1.2' 
        self.assertTrue(validate_state(state))  # Legacy four-format contract unchanged.


if __name__ == '__main__':
    unittest.main()
