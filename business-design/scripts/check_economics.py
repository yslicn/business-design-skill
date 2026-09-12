#!/usr/bin/env python3
"""Check declared arithmetic, references and scenario coverage; never evaluate code."""
import argparse
import json
import math
from pathlib import Path
from design_reliability import indexed, pointer


def check(ledger, business, market):
    errors = []
    evidence = set(indexed(market.get('evidence_registry', []), 'evidence_registry'))
    assumptions = set(indexed(business.get('assumptions', []), 'assumptions'))
    scenarios = ledger.get('scenarios', [])
    indexed(scenarios, 'scenarios')
    if not scenarios:
        return ['economics: at least one scenario required']
    for scenario in scenarios:
        sid = scenario['id']
        if any(not isinstance(scenario.get(k), str) or not scenario[k].strip()
               for k in ('basis', 'cash_conversion', 'decision_implication')):
            errors.append(sid + ': basis, cash_conversion and decision_implication required')
        values = {}
        inputs = indexed(scenario.get('inputs', []), sid + ' inputs')
        calculations = indexed(scenario.get('calculations', []), sid + ' calculations')
        if not inputs or not calculations or set(inputs) & set(calculations):
            errors.append(sid + ': nonempty disjoint input/calculation IDs required'); continue
        for key, row in inputs.items():
            value = row.get('value')
            refs, aids = row.get('evidence_ids', []), row.get('assumption_ids', [])
            if not isinstance(refs, list) or not isinstance(aids, list) or not (refs or aids) or any(x not in evidence for x in refs) or any(x not in assumptions for x in aids):
                errors.append(sid + '/' + key + ': missing or unknown input references')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not row.get('unit'):
                errors.append(sid + '/' + key + ': finite number and unit required'); continue
            values[key] = value
        for key, row in calculations.items():
            args, op = row.get('operands', []), row.get('operation')
            if not isinstance(args, list) or len(args) != 2 or any(a not in values for a in args) or op not in ('add', 'subtract', 'multiply', 'divide'):
                errors.append(sid + '/' + key + ': requires two existing operands and supported operation'); continue
            a, b = (values[x] for x in args)
            if op == 'divide' and b == 0:
                errors.append(sid + '/' + key + ': division by zero'); continue
            result = {'add': lambda: a+b, 'subtract': lambda: a-b, 'multiply': lambda: a*b, 'divide': lambda: a/b}[op]()
            claimed = row.get('result')
            if not math.isfinite(result) or isinstance(claimed, bool) or not isinstance(claimed, (int, float)) or not math.isfinite(claimed) or not math.isclose(result, claimed, rel_tol=1e-8, abs_tol=1e-8) or not row.get('unit'):
                errors.append(sid + '/' + key + ': result mismatch or missing unit')
            values[key] = result
        outputs = scenario.get('outputs', {})
        if not isinstance(outputs, dict) or any(outputs.get(k) not in calculations for k in ('revenue', 'contribution')):
            errors.append(sid + ': calculated revenue and contribution outputs required')
    covers = ledger.get('covers', [])
    if not isinstance(covers, list) or not covers:
        errors.append('economics: covers requires business JSON pointers')
    else:
        for path in covers:
            try:
                pointer(business, path)
            except (KeyError, IndexError, ValueError, TypeError):
                errors.append('economics: invalid coverage pointer ' + str(path))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ledger', 'business', 'market'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        errors = check(*(json.loads(p.read_text()) for p in (args.ledger, args.business, args.market)))
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError) as exc:
        errors = [str(exc)]
    print(json.dumps({'status': 'FAIL' if errors else 'PASS', 'errors': errors,
                      'scope': 'declared_arithmetic_and_references_only; units, assumptions and scenario relevance require review'}, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
