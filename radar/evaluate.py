"""Offline label scoring. python -m radar.evaluate predictions.json. No model calls."""
import json
import sys
from pathlib import Path


def evaluate(cases, predictions):
    expected = {case['id']: case for case in cases}
    ids = [row.get('id') for row in predictions]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError('Predictions must cover every case exactly once; unknown IDs are rejected')
    totals, failures = {}, []
    for row in predictions:
        case = expected[row['id']]
        group = totals.setdefault(case['stratum'], {'cases': 0, 'kind_correct': 0, 'codable_correct': 0})
        if type(row.get('codable')) is not bool or not isinstance(row.get('kind'), str):
            raise ValueError('Invalid prediction schema')
        group['cases'] += 1
        for field in ('kind', 'codable'):
            correct = row[field] == case['expected'][field]
            group[f'{field}_correct'] += correct
            if not correct:
                failures.append({'id': row['id'], 'field': field, 'expected': case['expected'][field], 'actual': row[field]})
    return {'synthetic_only': True, 'strata': totals, 'failures': failures,
            'not_measured': ['semantic citation accuracy', 'cluster independence', 'real buyer conversion']}


def main():
    cases = json.loads((Path(__file__).resolve().parents[1] / 'evals/commercial-cases.json').read_text())['cases']
    result = evaluate(cases, json.loads(Path(sys.argv[1]).read_text()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
