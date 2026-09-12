import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import design_reliability as d
import render_report_exhibits as ex
from export_content_report import export
from check_economics import check
import test_reliability_v31 as previous


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = previous.ReliabilityTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def test_rehashing_quality_does_not_reuse_old_review(self):
        q = self.fixture.bundle()
        self.fixture.write('business_design.md', 'new recommendation')
        q['source_hashes']['business_design.md'] = d.sha(self.root/'business_design.md')
        self.fixture.write('content_quality_report.json', q)
        errors = d.delivery(self.root)
        self.assertTrue(any('content_review_receipt.json: stale' in e for e in errors))
        self.assertTrue(any('stale export' in e for e in errors))

    def test_reviewed_docx_cannot_be_replaced_by_rehashing(self):
        q = self.fixture.bundle()
        self.fixture.write('business_design.docx', 'different word file')
        q['source_hashes']['business_design.docx'] = d.sha(self.root/'business_design.docx')
        self.fixture.write('content_quality_report.json', q)
        self.assertTrue(any('docx_review_receipt.json: stale' in e for e in d.delivery(self.root)))

    def test_malformed_dimensions_return_failure(self):
        for bad in (None, [], 'PASS'):
            q = self.fixture.bundle(); q['dimensions'] = bad
            self.fixture.write('content_quality_report.json', q)
            self.assertTrue(d.delivery(self.root))

    def test_invalid_pointer_cannot_be_keep_candidate(self):
        for path in ('/missing', '/items/-1', '/items/01', '/items/99'):
            with self.assertRaises(ValueError):
                d.impact({}, {}, {'items':[1,2]}, {'targets':[{'id':'summary','business_pointers':[path]}]})

    def test_duplicate_or_unknown_dependencies_fail(self):
        for bindings in ({'targets':[{'id':'a'},{'id':'a'}]}, {'targets':[{'id':'a','evidence_ids':['absent']}]}):
            with self.assertRaises(ValueError): d.impact({}, {}, {}, bindings)
        with self.assertRaises(ValueError):
            d.impact({'sources':[{'id':'S1'},{'id':'S1'}]}, {}, {}, {'targets':[]})

    def test_valid_unchanged_dependency_remains_candidate(self):
        result = d.impact({}, {}, {'selection':{}}, {'targets':[{'id':'a','business_pointers':['/selection']}]})
        self.assertEqual(result['targets'][0]['action'], 'keep_candidate')

    def test_partial_binding_and_empty_refs_not_verified(self):
        def render(e,b,data,path): path.write_bytes(b'test'); return 'fixture'
        plan={'exhibits':[{'id':'X1','type':'bar_ranking','action_title':'test','data':{'values':[999]},'data_bindings':{'labels':{'source':'business','pointer':'/labels'}}}]}
        p=self.fixture.write('plan.json',plan)
        with patch.dict(ex.RENDERERS, {'bar_ranking':render}):
            m=ex.render_plan(p,self.root/'exhibits',{'labels':['A']},{'evidence_registry':[]})
            self.assertEqual(m['exhibits'][0]['data_verification'],'partially_bound')
            self.assertIn('values',m['exhibits'][0]['unbound_fields'])
            self.assertFalse(m['evidence_refs_verified'])
            plan['exhibits'][0]['data']={}
            plan['exhibits'][0]['data_bindings']['values']={'source':'business','pointer':'/values'}
            plan['exhibits'][0]['source_refs']=['E1'];self.fixture.write('plan.json',plan)
            m=ex.render_plan(p,self.root/'exhibits',{'labels':['A'],'values':[12]},{'evidence_registry':[{'id':'E1'}]})
            self.assertEqual(m['exhibits'][0]['data_verification'],'source_bound')
            self.assertTrue(m['evidence_refs_verified'])

    @unittest.skipUnless(shutil.which('pandoc'),'pandoc required')
    def test_repeated_image_exports_twice_and_missing_image_fails(self):
        from PIL import Image
        from docx import Document
        Image.new('RGB',(80,40),'blue').save(self.root/'chart.png')
        source=self.fixture.write('report.md','# Test\n\n![First](chart.png)\n\n![Second](chart.png)\n')
        m=export(source,self.root/'output','PingFang SC')
        self.assertEqual(m['image_occurrences'],2)
        self.assertEqual(len(m['exhibits']),1)
        self.assertEqual(len(Document(self.root/'output/business_design.docx').inline_shapes),2)
        (self.root/'chart.png').unlink()
        with self.assertRaises(ValueError): export(source,self.root/'missing','PingFang SC')
        self.assertFalse((self.root/'missing').exists())

    def test_quantified_requires_ledger(self):
        self.fixture.bundle()
        self.fixture.write('business_design.json',{'chapters':{'profit_model':{'unit_economics':{'status':'quantified'}}}})
        self.assertIn('economics_ledger.json: required for quantified economics',d.delivery(self.root))


class EconomicsTests(unittest.TestCase):
    def fixture(self):
        row={'id':'base','basis':'CNY / month / unit','cash_conversion':'30 days, assumption','decision_implication':'validate cost',
             'inputs':[{'id':'price','value':100,'unit':'CNY/unit','evidence_ids':['E1']},{'id':'cost','value':60,'unit':'CNY/unit','assumption_ids':['A1']},{'id':'volume','value':20,'unit':'unit/month','assumption_ids':['A1']}],
             'calculations':[{'id':'revenue','operation':'multiply','operands':['price','volume'],'result':2000,'unit':'CNY/month'},{'id':'margin','operation':'subtract','operands':['price','cost'],'result':40,'unit':'CNY/unit'},{'id':'contribution','operation':'multiply','operands':['margin','volume'],'result':800,'unit':'CNY/month'}],
             'outputs':{'revenue':'revenue','contribution':'contribution'}}
        return {'covers':['/profit'],'scenarios':[row]}, {'profit':{},'assumptions':[{'id':'A1'}]}, {'evidence_registry':[{'id':'E1'}]}
    def test_correct_model(self):
        self.assertEqual(check(*self.fixture()),[])
    def test_wrong_arithmetic_unknown_source_and_zero_divisor(self):
        for mode in ('arithmetic','source','zero','nonfinite'):
            ledger,business,market=self.fixture();s=ledger['scenarios'][0]
            if mode=='arithmetic':s['calculations'][0]['result']=999
            elif mode=='source':s['inputs'][0]['evidence_ids']=['missing']
            elif mode=='zero':s['inputs'][2]['value']=0;s['calculations'][0]['operation']='divide'
            else:s['inputs'][0]['value']=float('nan')
            self.assertTrue(check(ledger,business,market),mode)

if __name__=='__main__':unittest.main()
