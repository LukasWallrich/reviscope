"""Summarize pooled-issue judging: which reports raise each paper's most important issues.

An issue counts as raised validly by a report when one of the report's points belongs to it
and both judges finally rate that point correct or partly correct. Consensus issues are those
both judges call established; consensus rank is the mean of each judge's relative rank.
"""
import argparse
import collections
import json
from pathlib import Path
import statistics

from judge_points import JUDGES, material, valid
from summarize_points import final

TOP = (5, 10)


def spearman(a, b):
    n = len(a)
    if n < 3:
        return None
    ra = {k: i for i, k in enumerate(a)}
    rb = {k: i for i, k in enumerate(b)}
    return round(1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in a) / (n * (n * n - 1)), 2)


def case_summary(result):
    groups = {f'i{n:03d}': g['item_ids'] for n, g in enumerate(result['groups'], 1)}
    rankings = result['rankings']
    assessed = {m: rankings[m]['assessments'] for m in JUDGES}
    both = [i for i in groups if all(assessed[m][i]['status'] == 'established' for m in JUDGES)]
    position = {m: {i: n / max(len(rankings[m]['ranking']) - 1, 1) for n, i in enumerate(rankings[m]['ranking'])}
                for m in JUDGES}
    consensus = sorted(both, key=lambda i: statistics.mean(position[m][i] for m in JUDGES))
    material_both = [i for i in both if all(material(assessed[m][i]['tier']) for m in JUDGES)]
    point_valid = {i: all(valid(final(result, m, i)['accuracy']) == 'valid' for m in JUDGES) for i in result['origins']}
    raised = collections.defaultdict(set)
    for issue, items in groups.items():
        for item in items:
            if point_valid[item]:
                raised[result['origins'][item]['report']].add(issue)
    reports = sorted({o['report'] for o in result['origins'].values()})
    rows = []
    for report in reports:
        row = {'case': result['case'], 'report': report, 'arm': report.split('/')[0],
               'issues_raised_validly': len(raised[report])}
        for k in TOP:
            row[f'top{k}_found'] = len(raised[report] & set(consensus[:k]))
        row['material_found'] = len(raised[report] & set(material_both))
        for m in JUDGES:
            own = {i for i in groups if assessed[m][i]['status'] == 'established' and material(assessed[m][i]['tier'])}
            row[f'material_found_{m.split("-")[0]}'] = len(raised[report] & own)
        rows.append(row)
    common = [i for i in rankings[JUDGES[0]]['ranking'] if i in both]
    other = [i for i in rankings[JUDGES[1]]['ranking'] if i in both]
    agreement = {
        'issues': len(groups), 'established_both': len(both), 'material_both': len(material_both),
        'material_by_judge': {m: sum(material(assessed[m][i]['tier']) and assessed[m][i]['status'] == 'established'
                                     for i in groups) for m in JUDGES},
        'status_agreement': round(sum(len({assessed[m][i]['status'] for m in JUDGES}) == 1 for i in groups) / len(groups), 2),
        'spearman_on_established_both': spearman(common, other),
        'top10_overlap': len(set(rankings[JUDGES[0]]['ranking'][:10]) & set(rankings[JUDGES[1]]['ranking'][:10]))}
    top = [{'issue_id': i, 'issue': result['groups'][int(i[1:]) - 1]['issue'],
            'tiers': {m.split('-')[0]: assessed[m][i]['tier'] for m in JUDGES},
            'raised_validly_by': sorted(r for r in reports if i in raised[r])} for i in consensus[:10]]
    return rows, agreement, top


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--judging-dir', default='judging-v2')
    args = parser.parse_args()
    directory = args.root / args.judging_dir
    rows, agreements, tops = [], {}, {}
    for path in sorted((directory / 'results').glob('*.json')):
        result = json.loads(path.read_text())
        case_rows, agreements[result['case']], tops[result['case']] = case_summary(result)
        rows += case_rows
    (directory / 'issue-summary.json').write_text(json.dumps({'reports': rows, 'agreement': agreements, 'top_issues': tops},
                                                             indent=2, ensure_ascii=False) + '\n')
    print('| Case | Report | Issues raised validly | Top 5 | Top 10 | Material (both) | Material (Opus) | Material (Sol) |')
    print('|---|---|--:|--:|--:|--:|--:|--:|')
    for r in rows:
        print(f"| {r['case']} | {r['report']} | {r['issues_raised_validly']} | {r['top5_found']} | {r['top10_found']} | "
              f"{r['material_found']} | {r['material_found_claude']} | {r['material_found_gpt']} |")
    print(json.dumps(agreements, indent=2))


if __name__ == '__main__':
    main()
