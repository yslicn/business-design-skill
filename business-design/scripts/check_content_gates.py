#!/usr/bin/env python3
"""Final report length, embedded exhibit and quantitative-content gates."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from audit_research_report import count_effective_length

EXCLUDED = re.compile(r'^(?:[一二三四五六七八九十\d]+[、.．\s]*)?(?:目录|附录|参考文献|参考资料|来源清单|来源索引|证据台账|来源与假设|参考来源|数据来源|references?\b|bibliography\b|appendix\b|table of contents\b)', re.I)


def plain(node):
    if isinstance(node, list):
        return ' '.join(plain(x) for x in node)
    if not isinstance(node, dict):
        return ''
    kind, value = node.get('t'), node.get('c')
    if kind == 'Str': return value
    if kind in ('Image', 'Note', 'Code', 'CodeBlock', 'RawBlock', 'RawInline', 'Math'): return ''
    if kind == 'Link': return plain(value[1])
    return plain(value)


def images(node):
    if isinstance(node, list):
        return [url for child in node for url in images(child)]
    if isinstance(node, dict):
        if node.get('t') == 'Image': return [node['c'][-1][0]]
        if node.get('t') in ('Note', 'CodeBlock', 'RawBlock'): return []
        return images(node.get('c'))
    return []


def body_blocks(blocks):
    skip_level = None
    for block in blocks:
        if block.get('t') == 'Header':
            level, _, title = block['c']
            if skip_level is not None and level <= skip_level: skip_level = None
            if EXCLUDED.match(plain(title).strip()): skip_level = level
            continue
        if skip_level is None and block.get('t') not in ('CodeBlock', 'RawBlock', 'HorizontalRule'):
            yield block


def numeric(value):
    if isinstance(value, bool): return False
    if isinstance(value, (int, float)):
        import math
        return math.isfinite(value)
    if isinstance(value, list): return any(numeric(x) for x in value)
    if isinstance(value, dict):
        return any(numeric(v) for k,v in value.items() if k not in ('id', 'evidence', 'source_refs', 'source_ids', 'assumption_ids'))
    return False


def inspect(blocks, known, valid_images, numeric_images):
    seen, total, image_urls, quantitative = set(), 0, set(), 0
    for block in body_blocks(blocks):
        text = plain(block)
        refs = set(re.findall(r'\[\s*([A-Za-z][A-Za-z0-9_-]*)\s*\]', text))
        clean = re.sub(r'\[\s*[A-Za-z][A-Za-z0-9_-]*\s*\]', '', text)
        clean = re.sub(r'https?://\S+', '', clean)
        canonical = re.sub(r'\s+', '', clean)
        if canonical and canonical not in seen:
            seen.add(canonical)
            total += count_effective_length(clean)['effective_count']
            # Years alone are not quantitative business content.
            figures = re.findall(r'(?<![A-Za-z\d])[-+]?\d+(?:\.\d+)?%?', clean)
            if refs & known and any(not re.fullmatch(r'(?:19|20)\d{2}', x) for x in figures):
                quantitative += 1
        image_urls.update(images(block))
    embedded = image_urls & valid_images
    quantitative += len(embedded & numeric_images)
    errors = []
    if not 10000 <= total <= 15000:
        errors.append(f'content length: {total}; required 10000..15000 effective body words/characters')
    if not embedded: errors.append('content visuals: at least one embedded, verified plan exhibit required in body')
    if not quantitative: errors.append('content data: evidence-linked quantitative body content or exhibit required')
    return {'effective_body_count': total, 'body_exhibits': sorted(embedded),
            'quantitative_blocks_or_exhibits': quantitative, 'errors': errors}


def audit_content(root, md_path, market):
    root, md_path = Path(root), Path(md_path)
    try:
        parsed = subprocess.run(['pandoc',str(md_path),'-f','markdown-yaml_metadata_block-smart','-t','json'],check=True,capture_output=True,text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError('content gates: cannot parse manuscript with pandoc: ' + str(exc)) from exc
    blocks = json.loads(parsed.stdout)['blocks']
    known = {x['id'] for x in market.get('evidence_registry', [])}
    valid, quantitative = set(), set()
    pp, mp = root/'exhibit_plan.json', root/'exhibits/exhibits_manifest.json'
    if pp.is_file() and mp.is_file():
        from design_reliability import resolve_data
        plan = json.loads(pp.read_text())
        manifest = json.loads(mp.read_text())
        business = {}
        quality_path = root/'content_quality_report.json'
        quality = json.loads(quality_path.read_text()) if quality_path.is_file() else {}
        bp = root/quality.get('artifact_paths', {}).get('business_design.json','business_design.json')
        if bp.is_file(): business = json.loads(bp.read_text())
        planned = {x['id']:x for x in plan.get('exhibits',[])}
        for row in manifest.get('exhibits',[]):
            exhibit = planned.get(row.get('id'))
            if not exhibit: continue
            png = root/row['png']
            if not png.is_file() or hashlib.sha256(png.read_bytes()).hexdigest() != row.get('sha256'): continue
            from PIL import Image
            try:
                with Image.open(png) as picture: picture.verify()
            except (OSError, ValueError): continue
            # Compare resolved local paths, so both root MD and versioned MD work.
            urls = [url for block in body_blocks(blocks) for url in images(block)]
            matched = {url for url in urls if (md_path.parent/url).is_file()
                       and hashlib.sha256((md_path.parent/url).read_bytes()).hexdigest() == row.get('sha256')}
            valid.update(matched)
            refs = exhibit.get('source_refs', [])
            data = resolve_data(exhibit,business,market)
            if refs and set(refs).issubset(known) and numeric(data): quantitative.update(matched)
    result = inspect(blocks,known,valid,quantitative)
    result.update(status='FAIL' if result['errors'] else 'PASS',scope='length_and_structural_presence; semantic_density_and_data_truth_require_review')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);args=p.parse_args()
    try:
        root=args.project
        qpath=root/'content_quality_report.json'
        q=json.loads(qpath.read_text()) if qpath.is_file() else {}
        paths=q.get('artifact_paths',{})
        result=audit_content(root,root/paths.get('business_design.md','business_design.md'),json.loads((root/paths.get('market_insight.json','market_insight.json')).read_text()))
    except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError,subprocess.CalledProcessError) as exc:
        result={'status':'FAIL','errors':[str(exc)]}
    print(json.dumps(result,ensure_ascii=False,indent=2));return int(result['status']=='FAIL')

if __name__=='__main__': raise SystemExit(main())
