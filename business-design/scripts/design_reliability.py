#!/usr/bin/env python3
"""Read-only delivery validation, evidence handoff and scoped change candidates."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pointer(doc, path):
    if not isinstance(path, str):
        raise ValueError('JSON pointer must be a string')
    if path == '':
        return doc
    if not path.startswith('/'):
        raise ValueError('JSON pointer must start with /')
    for key in path[1:].split('/'):
        key = key.replace('~1', '/').replace('~0', '~')
        if isinstance(doc, list):
            if not key.isdigit() or (len(key) > 1 and key.startswith('0')):
                raise ValueError('invalid array index in JSON pointer')
            doc = doc[int(key)]
        else:
            doc = doc[key]
    return doc


def resolve_data(exhibit, business, market):
    """Bind top-level renderer input fields to a source JSON pointer."""
    data = copy.deepcopy(exhibit.get('data', {}))
    bindings = exhibit.get('data_bindings', {})
    if not isinstance(bindings, dict):
        raise ValueError('data_bindings must be an object')
    for field, binding in bindings.items():
        if not isinstance(binding, dict) or binding.get('source') not in ('business', 'market'):
            raise ValueError('binding requires source business|market and pointer')
        source = business if binding['source'] == 'business' else market
        if source is None:
            raise ValueError('bound source not supplied')
        value = copy.deepcopy(pointer(source, binding['pointer']))
        if field in data and data[field] != value:
            raise ValueError('inline value differs from bound source: ' + field)
        data[field] = value
    return data


def evidence_package(path):
    doc = load(path)
    items = doc if isinstance(doc, list) else doc.get('items')
    if not isinstance(items, list):
        raise ValueError('upstream requires list or items array')
    ids = [x.get('id') for x in items]
    if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('upstream evidence IDs missing or duplicated')
    return {'schema_version': '1.0', 'upstream_path': str(Path(path).resolve()),
            'upstream_sha256': sha(path), 'items': copy.deepcopy(items),
            'review_reused': False, 'business_readiness_verified': False,
            'missing_fields': {x['id']: [k for k in ('kind', 'locator') if not x.get(k)] for x in items
                               if not x.get('kind') or not x.get('locator')}}



def verify_mapping(data_path, market_path, map_path):
    package = evidence_package(data_path)
    market, mapping = load(market_path), load(map_path)
    if mapping.get('upstream_sha256') != package['upstream_sha256']:
        raise ValueError('evidence mapping references stale upstream data')
    upstream = {x['id'] for x in package['items']}
    local = {x['id']: x for x in market.get('evidence_registry', [])}
    sources = {x['id'] for x in market.get('sources', [])}
    entries = mapping.get('mappings')
    if not isinstance(entries, list) or not entries:
        raise ValueError('nonempty evidence mappings required')
    seen = set()
    for row in entries:
        pair = (row.get('upstream_id'), row.get('local_evidence_id'))
        if pair in seen or pair[0] not in upstream or pair[1] not in local:
            raise ValueError('duplicate or dangling evidence mapping')
        seen.add(pair)
        ids = row.get('source_ids', [])
        if not ids or not set(ids).issubset(sources) or not set(ids).issubset(set(local[pair[1]].get('source_ids', []))):
            raise ValueError('mapped sources do not match local evidence sources')
    return {'status': 'PASS', 'mapped_pairs': len(seen), 'scope': 'identity_and_hash_checks_only',
            'unmapped_upstream_ids': sorted(upstream - {a for a, b in seen}),
            'semantic_equivalence_verified': False}


def object_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def delivery(project, state=None):
    root = Path(project).resolve()
    q = load(root / 'content_quality_report.json')
    errors = []
    if not isinstance(q, dict):
        raise ValueError('quality report must be an object')
    for field in ('dimensions', 'source_hashes', 'artifact_paths'):
        if not isinstance(q.get(field, {}), dict):
            return [field + ': must be an object']
    dimensions = q.get('dimensions', {})
    for name in ('viewpoint', 'argument', 'argument_sufficiency', 'evidence', 'tradeoffs', 'economics_execution', 'readability'):
        row = dimensions.get(name, {})
        if not isinstance(row, dict):
            errors.append(name + ': must be an object'); continue
        score = row.get('score')
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 4 <= score <= 5 or not str(row.get('rationale', '')).strip():
            errors.append(name + ': reviewed score 4..5 and rationale required')
    for name in ('status', 'independent_review', 'md_json_consistency', 'docx_text_fidelity', 'docx_readability'):
        if q.get(name) != 'PASS':
            errors.append(name + ' is not PASS')
    if q.get('blocking_issues') != []:
        errors.append('blocking_issues must be explicitly empty')
    hashes = q.get('source_hashes', {})
    names = {n: n for n in ('business_design.md', 'business_design.json', 'business_design.docx', 'market_insight.json', 'review_notes.md')}
    overrides = q.get('artifact_paths', {})
    for key in names:
        names[key] = overrides.get(key, names[key])
    names['docx_review_record'] = q.get('docx_review_artifact')
    for key, rel in names.items():
        if not isinstance(rel, str) or not rel:
            errors.append(key + ': path missing'); continue
        p = (root / rel).resolve()
        if not p.is_file():
            errors.append(key + ': file missing'); continue
        if hashes.get(key) != sha(p):
            errors.append(key + ': hash mismatch')
    business_path = root / names['business_design.json']
    market_path = root / names['market_insight.json']
    if business_path.is_file() and market_path.is_file():
        business, market = load(business_path), load(market_path)
        profit = business.get('chapters', {}).get('profit_model', {})
        quantified = ['/chapters/profit_model/' + key for key in ('unit_economics', 'profitability_estimate')
                      if profit.get(key, {}).get('status') == 'quantified']
        ledger_path = root / 'economics_ledger.json'
        if quantified and not ledger_path.is_file():
            errors.append('economics_ledger.json: required for quantified economics')
        if ledger_path.is_file():
            from check_economics import check
            ledger = load(ledger_path)
            errors.extend(check(ledger, business, market))
            if not set(quantified).issubset(set(ledger.get('covers', []))):
                errors.append('economics ledger does not cover quantified sections')
            if quantified and len(ledger.get('scenarios', [])) < 2:
                errors.append('quantified economics requires base and sensitivity scenarios')
    md_path = root / names['business_design.md']
    if md_path.is_file() and market_path.is_file():
        from check_content_gates import audit_content
        errors.extend(audit_content(root, md_path, load(market_path))['errors'])
    # Receipts are written by the actual reviewer, not generated from PASS flags.
    for receipt_name, required in (
        ('content_review_receipt.json', ('business_design.md', 'business_design.json', 'market_insight.json', 'review_notes.md')),
        ('docx_review_receipt.json', ('business_design.md', 'business_design.docx', 'docx_review_record')),
    ):
        receipt_path = root / receipt_name
        if not receipt_path.is_file():
            errors.append(receipt_name + ': reviewer receipt missing'); continue
        receipt = load(receipt_path)
        if not isinstance(receipt, dict) or receipt.get('status') != 'PASS' or not receipt.get('reviewer'):
            errors.append(receipt_name + ': reviewer and PASS required'); continue
        reviewed = receipt.get('reviewed_hashes', {})
        if not isinstance(reviewed, dict):
            errors.append(receipt_name + ': reviewed_hashes must be an object'); continue
        if receipt_name == 'content_review_receipt.json' and (root / 'economics_ledger.json').is_file():
            required += ('economics_ledger.json',)
        for key in required:
            rel = names.get(key, key)
            if not rel or not (root / rel).is_file() or reviewed.get(key) != sha(root / rel):
                errors.append(receipt_name + ': stale reviewed version: ' + key)
    docx_path = root / names['business_design.docx']
    export_path = docx_path.parent / 'report_manifest.json'
    if not export_path.is_file():
        errors.append('report_manifest.json: export provenance missing')
    else:
        exported = load(export_path)
        if exported.get('conversion_status') != 'PASS':
            errors.append('report_manifest.json: conversion not PASS')
        for key in ('business_design.md', 'business_design.docx'):
            actual = root / names[key]
            if not actual.is_file() or exported.get('artifacts', {}).get(key, {}).get('sha256') != sha(actual):
                errors.append('report_manifest.json: stale export: ' + key)
        for row in exported.get('exhibits', []):
            image_path = docx_path.parent / row['path']
            if not image_path.is_file() or sha(image_path) != row.get('sha256'):
                errors.append('report_manifest.json: exported image changed: ' + row['path'])
    if state is not None:
        for key in ('business_design.md', 'business_design.json', 'business_design.docx', 'content_quality_report.json'):
            registered = state.get('core_artifacts', {}).get(key, {}).get('path')
            expected = names.get(key, key)
            if not registered or (root / registered).resolve() != (root / expected).resolve():
                errors.append(key + ': state path differs from verified artifact')
    if q.get('review_artifact') != 'review_notes.md':
        errors.append('review_artifact must identify checked review_notes.md')
    if (root / 'exhibits/exhibits_manifest.json').exists() and not (root / 'exhibit_plan.json').is_file():
        errors.append('exhibit_plan.json: missing for existing exhibit manifest')
    if (root / 'exhibit_plan.json').exists():
        for rel in ('exhibit_plan.json', 'exhibits/exhibits_manifest.json'):
            p = root / rel
            if not p.is_file() or hashes.get(rel) != sha(p):
                errors.append(rel + ': missing or stale exhibit hash')
        mp = root / 'exhibits/exhibits_manifest.json'
        if mp.exists():
            manifest = load(mp)
            if manifest.get('plan_sha256') != sha(root / 'exhibit_plan.json'):
                errors.append('exhibit plan provenance mismatch')
            for key, artifact in [('business_object_sha256', 'business_design.json'), ('market_object_sha256', 'market_insight.json')]:
                source = root / names[artifact]
                if not source.is_file() or manifest.get(key) != object_sha(load(source)):
                    errors.append(key + ': exhibit source changed; rerender required')
            planned = load(root / 'exhibit_plan.json').get('exhibits', [])
            actual = manifest.get('exhibits', [])
            planned_ids = [x['id'] for x in planned]
            actual_ids = [x['id'] for x in actual]
            if not planned_ids or len(set(actual_ids)) != len(actual_ids) or set(planned_ids) != set(actual_ids):
                errors.append('exhibit manifest does not cover plan')
            for row in actual:
                p = root / row['png']
                if not p.is_file() or sha(p) != row.get('sha256'):
                    errors.append(row.get('id', '?') + ': stale exhibit PNG')
    return errors


def indexed(rows, label):
    if not isinstance(rows, list) or any(not isinstance(x, dict) or not isinstance(x.get('id'), str) or not x['id'] for x in rows):
        raise ValueError(label + ': requires objects with nonempty IDs')
    result = {x['id']: x for x in rows}
    if len(result) != len(rows):
        raise ValueError(label + ': duplicate IDs')
    return result


def changed_ids(before, after, key):
    a = indexed(before.get(key, []), key)
    b = indexed(after.get(key, []), key)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def impact(before, after, business, bindings):
    changed = set(changed_ids(before, after, 'evidence_registry'))
    changed_sources = set(changed_ids(before, after, 'sources'))
    for x in before.get('evidence_registry', []) + after.get('evidence_registry', []):
        if changed_sources.intersection(x.get('source_ids', [])):
            changed.add(x['id'])
    paths = []
    def walk(node, path):
        if isinstance(node, dict):
            if changed.intersection(node.get('evidence_ids', [])):
                paths.append(path)
            for k, v in node.items():
                walk(v, path + '/' + k.replace('~', '~0').replace('/', '~1'))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + '/' + str(i))
    walk(business, '')
    targets = []
    indexed(bindings.get('targets', []), 'targets')
    known_evidence = set(indexed(before.get('evidence_registry', []), 'evidence_registry')) | set(indexed(after.get('evidence_registry', []), 'evidence_registry'))
    for target in bindings.get('targets', []):
        refs = target.get('evidence_ids', [])
        if not isinstance(refs, list) or any(not isinstance(x, str) or x not in known_evidence for x in refs):
            raise ValueError(target['id'] + ': invalid evidence dependency')
        direct = bool(changed.intersection(refs))
        source_paths = target.get('business_pointers', [])
        if not isinstance(source_paths, list):
            raise ValueError(target['id'] + ': business_pointers must be an array')
        for path in source_paths:
            try:
                pointer(business, path)
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise ValueError(target['id'] + ': invalid business dependency: ' + str(path)) from exc
        affected = direct or any(a == b or a.startswith(b + '/') or b.startswith(a + '/') for a in paths for b in source_paths)
        targets.append({'id': target['id'], 'action': 'review' if affected else 'check_dependencies' if not source_paths and not target.get('evidence_ids') else 'keep_candidate'})
    return {'changed_evidence_ids': sorted(changed), 'business_pointers': paths,
            'targets': targets, 'global_summary_and_recommendation_review_required': True,
            'scope': 'declared_dependencies_only', 'automatic_rewrite': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest='command', required=True)
    a = s.add_parser('delivery'); a.add_argument('--project', required=True)
    a = s.add_parser('evidence'); a.add_argument('--data', required=True)
    a = s.add_parser('mapping')
    for n in ('data', 'market', 'map'):
        a.add_argument('--' + n, required=True)
    a = s.add_parser('impact')
    for n in ('before', 'after', 'business', 'bindings'):
        a.add_argument('--' + n, required=True)
    args = p.parse_args()
    try:
        if args.command == 'delivery':
            errors = delivery(args.project)
            result = {'status': 'FAIL' if errors else 'PASS', 'errors': errors, 'scope': 'file_and_declared_status_checks_only'}
        elif args.command == 'evidence':
            result = evidence_package(args.data)
        elif args.command == 'mapping':
            result = verify_mapping(args.data, args.market, args.map)
        else:
            result = impact(load(args.before), load(args.after), load(args.business), load(args.bindings))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result.get('status') == 'FAIL')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        print(json.dumps({'status': 'FAIL', 'errors': [str(exc)]}, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
