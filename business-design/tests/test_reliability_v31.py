import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import design_reliability as d
import render_report_exhibits as ex

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        gate = patch('check_content_gates.audit_content', return_value={'errors': []})
        gate.start(); self.addCleanup(gate.stop)
    def write(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(value if isinstance(value,str) else json.dumps(value));return p
    def bundle(self):
        names=['business_design.md','business_design.json','business_design.docx','market_insight.json','review_notes.md','visual.md']
        for n in names:self.write(n,{} if n.endswith('.json') else 'synthetic fixture '+n)
        q=dict(status='PASS',independent_review='PASS',md_json_consistency='PASS',docx_text_fidelity='PASS',docx_readability='PASS',blocking_issues=[],review_artifact='review_notes.md',docx_review_artifact='visual.md')
        q['source_hashes']={n:d.sha(self.root/n) for n in names[:-1]};q['source_hashes']['docx_review_record']=d.sha(self.root/'visual.md')
        q['dimensions']={n:dict(score=4,rationale='fixture reviewed') for n in ['viewpoint','argument','argument_sufficiency','evidence','tradeoffs','economics_execution','readability']}
        self.write('content_review_receipt.json',dict(status='PASS',reviewer='fixture reviewer',reviewed_hashes={n:d.sha(self.root/n) for n in ['business_design.md','business_design.json','market_insight.json','review_notes.md']}))
        self.write('docx_review_receipt.json',dict(status='PASS',reviewer='fixture visual reviewer',reviewed_hashes={'business_design.md':d.sha(self.root/'business_design.md'),'business_design.docx':d.sha(self.root/'business_design.docx'),'docx_review_record':d.sha(self.root/'visual.md')}))
        self.write('report_manifest.json',dict(conversion_status='PASS',artifacts={n:{'sha256':d.sha(self.root/n)} for n in ['business_design.md','business_design.docx']}))
        self.write('content_quality_report.json',q);return q
    def test_valid_file_checks(self):
        self.bundle();self.assertEqual(d.delivery(self.root),[])
    def test_changed_manuscript_rejects_old_pass(self):
        self.bundle();self.write('business_design.md','changed');self.assertTrue(d.delivery(self.root))
    def test_missing_word_rejected(self):
        self.bundle();(self.root/'business_design.docx').unlink();self.assertTrue(d.delivery(self.root))
    def test_missing_review_record_rejected(self):
        self.bundle();(self.root/'visual.md').unlink();self.assertTrue(d.delivery(self.root))
    def test_low_dimension_cannot_average_out(self):
        q=self.bundle();q['dimensions']['evidence']['score']=3;self.write('content_quality_report.json',q);self.assertTrue(d.delivery(self.root))
    def test_nonempty_blockers_rejected(self):
        q=self.bundle();q['blocking_issues']=['unresolved'];self.write('content_quality_report.json',q);self.assertTrue(d.delivery(self.root))
    def test_export_subdirectory(self):
        q=self.bundle();(self.root/'v2').mkdir();(self.root/'business_design.docx').rename(self.root/'v2/business_design.docx')
        (self.root/'report_manifest.json').rename(self.root/'v2/report_manifest.json')
        q['artifact_paths']={'business_design.docx':'v2/business_design.docx'};self.write('content_quality_report.json',q);self.assertEqual(d.delivery(self.root),[])
    def test_state_cannot_point_to_other_file(self):
        self.bundle();state={'core_artifacts':{n:{'path':n} for n in ['business_design.md','business_design.json','business_design.docx','content_quality_report.json']}}
        self.assertEqual(d.delivery(self.root,state),[]);state['core_artifacts']['business_design.md']['path']='other.md';self.assertTrue(d.delivery(self.root,state))
    def test_evidence_preserves_id_and_pending(self):
        row={'id':'R1-01','value':'unverified','review_status':'pending'}
        for doc in [[row],{'schema_version':'4.0','items':[row]}]:
            p=self.write('data.json',doc);h=d.sha(p);result=d.evidence_package(p)
            self.assertEqual(result['items'],[row]);self.assertFalse(result['review_reused']);self.assertEqual(d.sha(p),h)
    def test_mapping_checks_ids_and_revision(self):
        up=self.write('up.json',{'items':[{'id':'D1','value':'test'}]})
        market=self.write('market.json',{'sources':[{'id':'S1'}],'evidence_registry':[{'id':'E1','source_ids':['S1']}]})
        mapping={'upstream_sha256':d.sha(up),'mappings':[{'upstream_id':'D1','local_evidence_id':'E1','source_ids':['S1']}]}
        mp=self.write('map.json',mapping)
        self.assertEqual(d.verify_mapping(up,market,mp)['status'],'PASS')
        self.write('up.json',{'items':[{'id':'D1','value':'changed'}]})
        with self.assertRaises(ValueError):d.verify_mapping(up,market,mp)
    def test_mapping_cannot_reassign_source(self):
        up=self.write('up.json',[{'id':'D1'}]);market=self.write('market.json',{'sources':[{'id':'S1'},{'id':'S2'}],'evidence_registry':[{'id':'E1','source_ids':['S1']}]})
        mp=self.write('map.json',{'upstream_sha256':d.sha(up),'mappings':[{'upstream_id':'D1','local_evidence_id':'E1','source_ids':['S2']}]})
        with self.assertRaises(ValueError):d.verify_mapping(up,market,mp)
    def test_duplicate_upstream_rejected(self):
        p=self.write('data.json',[{'id':'D1'},{'id':'D1'}])
        with self.assertRaises(ValueError):d.evidence_package(p)
    def test_binding_reads_exact_values(self):
        x={'data_bindings':{'values':{'source':'market','pointer':'/a~1b/0'}}}
        self.assertEqual(d.resolve_data(x,None,{'a/b':[[2,3]]})['values'],[2,3])
    def test_inline_conflict_rejected(self):
        x={'data':{'values':[9]},'data_bindings':{'values':{'source':'market','pointer':'/v'}}}
        with self.assertRaises(ValueError):d.resolve_data(x,None,{'v':[2]})
    def test_missing_pointer_not_silently_zero(self):
        with self.assertRaises(KeyError):d.resolve_data({'data_bindings':{'values':{'source':'market','pointer':'/v'}}},None,{})
    def test_source_change_propagates_to_business_and_summary(self):
        old={'sources':[{'id':'S1','url':'old'}],'evidence_registry':[{'id':'E1','source_ids':['S1']}]}
        new=copy.deepcopy(old);new['sources'][0]['url']='new'
        business={'chapters':{'selection':{'evidence_ids':['E1']}}}
        result=d.impact(old,new,business,{'targets':[{'id':'summary','business_pointers':['/chapters/selection']}]})
        self.assertEqual(result['changed_evidence_ids'],['E1']);self.assertEqual(result['targets'][0]['action'],'review')
    def test_empty_dependencies_require_check(self):
        result=d.impact({}, {}, {}, {'targets':[{'id':'summary'}]});self.assertEqual(result['targets'][0]['action'],'check_dependencies')
    def test_nondefault_weight_labels(self):
        biz={'chapters':{'customer_selection':{'selection_method':{'market_attractiveness_weight':0.6,'enterprise_fit_weight':0.4},'segment_evaluation':[{'segment':'A','weighted_score':4,'market_attractiveness_contribution':2.4,'enterprise_fit_contribution':1.6}]}}}
        fig,ax=MagicMock(),MagicMock()
        with patch.object(ex,'_bar_axes',return_value=(fig,ax)),patch.object(ex,'_finish'):
            ex.render_contribution_stack({'id':'X1'},biz,self.root/'x.png')
        labels=[c.kwargs['label'] for c in ax.barh.call_args_list]
        self.assertIn('60%',labels[0]);self.assertIn('40%',labels[1])
    def test_stale_exhibit_source_is_rejected(self):
        q=self.bundle();plan=self.write('exhibit_plan.json',{'exhibits':[{'id':'X1'}]});png=self.write('exhibits/X1.png','fixture')
        m=dict(plan_sha256=d.sha(plan),business_object_sha256=d.object_sha({}),market_object_sha256=d.object_sha({}),exhibits=[dict(id='X1',png='exhibits/X1.png',sha256=d.sha(png))])
        mp=self.write('exhibits/exhibits_manifest.json',m)
        for n in ['exhibit_plan.json','exhibits/exhibits_manifest.json']:q['source_hashes'][n]=d.sha(self.root/n)
        self.write('content_quality_report.json',q);self.assertEqual(d.delivery(self.root),[])
        self.write('market_insight.json',{'changed':True});q['source_hashes']['market_insight.json']=d.sha(self.root/'market_insight.json');self.write('content_quality_report.json',q)
        self.assertTrue(any('rerender' in e for e in d.delivery(self.root)))

if __name__=='__main__':unittest.main()
