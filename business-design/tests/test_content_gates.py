import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_content_gates import inspect,audit_content

def para(text):return {'t':'Para','c':[{'t':'Str','c':text}]}
def header(text,level=1):return {'t':'Header','c':[level,['',[],[]],[{'t':'Str','c':text}]]}
def image():return {'t':'Para','c':[{'t':'Image','c':[['',[],[]],[],['exhibits/X1.png','']]}]}

class ContentGatesTests(unittest.TestCase):
    def test_inclusive_length_boundaries(self):
        for count,passed in ((9999,False),(10000,True),(15000,True),(15001,False)):
            result=inspect([para('文'*count),image()],{'E1'},{'exhibits/X1.png'},{'exhibits/X1.png'})
            self.assertEqual(not result['errors'],passed)
    def test_plain_text_is_not_enough(self):
        result=inspect([para('文'*10000)],set(),set(),set())
        self.assertTrue(any('visuals' in x for x in result['errors']))
        self.assertTrue(any('data' in x for x in result['errors']))
    def test_concept_image_needs_quantitative_content(self):
        result=inspect([para('文'*10000),image()],set(),{'exhibits/X1.png'},set())
        self.assertTrue(any('data' in x for x in result['errors']))
    def test_cited_number_can_supply_data(self):
        result=inspect([para('文'*10000),para('价格 100 元 [E1]'),image()],{'E1'},{'exhibits/X1.png'},set())
        self.assertEqual(result['errors'],[])
    def test_years_unknown_citations_and_ids_do_not_supply_data(self):
        for text in ('年份 2026 [E1]','收入 100 元 [E99]','[E1]'):
            result=inspect([para('文'*10000),para(text),image()],{'E1'},{'exhibits/X1.png'},set())
            self.assertTrue(any('data' in x for x in result['errors']))
    def test_references_appendix_code_and_repetitions_excluded(self):
        result=inspect([para('正文'*100),para('正文'*100),{'t':'CodeBlock','c':[['',[],[]],'代码'*10000]},header('附录'),para('附录内容'*10000),image()],set(),{'exhibits/X1.png'},set())
        self.assertEqual(result['effective_body_count'],200)
        self.assertEqual(result['body_exhibits'],[])
    def test_resume_after_toc_and_ignore_alt_text(self):
        result=inspect([header('目录'),para('目录内容'*10000),header('业务分析'),para('正'*10000),image()],set(),{'exhibits/X1.png'},set())
        self.assertEqual(result['effective_body_count'],10000)
    @unittest.skipUnless(shutil.which('pandoc'),'pandoc required')
    def test_real_markdown_image_and_plan(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);(r/'exhibits').mkdir();png=r/'exhibits/X1.png';Image.new('RGB',(20,20),'blue').save(png)
            (r/'business_design.md').write_text('# 业务分析\n\n'+'分析'*5000+'\n\n销售额为100万元 [E1]。\n\n![X1 分析](exhibits/X1.png)\n')
            (r/'exhibit_plan.json').write_text(json.dumps({'exhibits':[{'id':'X1','type':'bar_ranking','source_refs':['E1'],'data':{'labels':['A'],'values':[100]}}]}))
            (r/'exhibits/exhibits_manifest.json').write_text(json.dumps({'exhibits':[{'id':'X1','png':'exhibits/X1.png','sha256':hashlib.sha256(png.read_bytes()).hexdigest()}]}))
            market={'evidence_registry':[{'id':'E1'}]}
            self.assertEqual(audit_content(r,r/'business_design.md',market)['status'],'PASS')
            png.write_bytes(b'not an image')
            self.assertEqual(audit_content(r,r/'business_design.md',market)['status'],'FAIL')

if __name__=='__main__':unittest.main()
