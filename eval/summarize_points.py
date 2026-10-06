"""Summarize point-level judging: per-report counts, arm means, judge agreement and reasons."""
import argparse
import collections
import json
from pathlib import Path
import statistics

from judge_points import JUDGES, material, valid


def final(result, model, item):
    label = dict(result['labels'][model][item])
    label.update({k: v for k, v in result['resolutions'][model].get(item, {}).items() if k in ('accuracy', 'importance')})
    return label


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    observed = sum(a == b for a, b in pairs) / n
    left, right = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in left) / n ** 2
    return None if expected == 1 else round((observed - expected) / (1 - expected), 2)


def report_rows(result):
    by_report = collections.defaultdict(list)
    for item, origin in result['origins'].items():
        by_report[origin['report']].append(item)
    group_of = {i: n for n, g in enumerate(result['groups']) for i in g['item_ids']}
    rows = []
    for report, items in sorted(by_report.items()):
        row = {'case': result['case'], 'report': report, 'arm': report.split('/')[0], 'points': len(items)}
        agreed = [i for i in items if all(valid(final(result, m, i)['accuracy']) == 'valid'
                                          and material(final(result, m, i)['importance']) for m in JUDGES)]
        row['valid_material_both'] = len(agreed)
        row['unique_issues_valid_material_both'] = len({group_of[i] for i in agreed})
        row['incorrect_either'] = sum(any(final(result, m, i)['accuracy'] == 'incorrect' for m in JUDGES) for i in items)
        row['reasoning_valid_material_both'] = sum(all(result['labels'][m][i]['category'] == 'reasoning_coherence'
                                                       for m in JUDGES) for i in agreed)
        for m in JUDGES:
            short = m.split('-')[0]
            labels = [final(result, m, i) for i in items]
            row[f'valid_material_{short}'] = sum(valid(l['accuracy']) == 'valid' and material(l['importance']) for l in labels)
            row[f'incorrect_{short}'] = sum(l['accuracy'] == 'incorrect' for l in labels)
            row[f'excessive_remedy_{short}'] = sum(result['labels'][m][i]['remedy'] == 'excessive' for i in items)
        modules = collections.Counter(result['origins'][i].get('module') for i in agreed)
        row['valid_material_both_by_module'] = {k: v for k, v in modules.items() if k}
        rows.append(row)
    return rows


def agreement(results):
    out = {}
    for stage in ('initial', 'final'):
        pick = (lambda r, m, i: r['labels'][m][i]) if stage == 'initial' else final
        validity, materiality, exact = [], [], []
        for r in results:
            for i in r['origins']:
                a, b = (pick(r, m, i) for m in JUDGES)
                validity.append((valid(a['accuracy']), valid(b['accuracy'])))
                materiality.append((material(a['importance']), material(b['importance'])))
                exact.append((a['importance'], b['importance']))
        out[stage] = {'points': len(validity),
                      'validity_agreement': round(sum(a == b for a, b in validity) / len(validity), 3),
                      'validity_kappa': kappa(validity),
                      'materiality_agreement': round(sum(a == b for a, b in materiality) / len(materiality), 3),
                      'materiality_kappa': kappa(materiality),
                      'importance_exact_agreement': round(sum(a == b for a, b in exact) / len(exact), 3)}
    reasons = {m: collections.Counter(x['reason'] for r in results for x in r['resolutions'][m].values()) for m in JUDGES}
    changed = {m: sum(x['changed'] for r in results for x in r['resolutions'][m].values()) for m in JUDGES}
    disputed = sum(len(r['resolutions'][JUDGES[0]]) for r in results)
    return {**out, 'disputed_points': disputed, 'changed_after_seeing_other': changed,
            'reasons': {m: dict(c.most_common()) for m, c in reasons.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    results = [json.loads(p.read_text()) for p in sorted((args.root / 'judging' / 'results').glob('*.json'))]
    rows = [row for r in results for row in report_rows(r)]
    keys = ['points', 'valid_material_both', 'unique_issues_valid_material_both', 'reasoning_valid_material_both',
            'incorrect_either', *[k for k in rows[0] if k.startswith(('valid_material_claude', 'valid_material_gpt'))]]
    arms = {}
    by = collections.defaultdict(list)
    for row in rows:
        by[(row['case'], row['arm'])].append(row)
    for (case, arm), group in sorted(by.items()):
        arms[f'{case}/{arm}'] = {k: round(statistics.mean(r[k] for r in group), 1) for k in keys}
        arms[f'{case}/{arm}']['reports'] = len(group)
    summary = {'reports': rows, 'case_arm_means': arms, 'agreement': agreement(results)}
    (args.root / 'judging' / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    lines = ['| Case | Report | Points | Valid & material (both) | Unique issues | Reasoning | Incorrect (either) | Opus V&M | Sol V&M |',
             '|---|---|--:|--:|--:|--:|--:|--:|--:|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['report']} | {r['points']} | {r['valid_material_both']} | "
                     f"{r['unique_issues_valid_material_both']} | {r['reasoning_valid_material_both']} | {r['incorrect_either']} | "
                     f"{r['valid_material_claude']} | {r['valid_material_gpt']} |")
    print('\n'.join(lines))
    print(json.dumps(summary['agreement'], indent=2))


if __name__ == '__main__':
    main()
