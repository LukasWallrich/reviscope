"""Point-level review scoring by two judge families, with tracked disagreement reasons.

Every report becomes a list of points: published pipeline findings, plain-review issues, or
free-text human reviews parsed by a model into points whose verbatim excerpts are checked
against the review. Points from all reports on a paper are shuffled and blinded. Opus and Sol
each label every point for accuracy, importance, remedy burden and category against the
manuscript. Where they disagree on validity or materiality, each sees the other's anonymised
assessment, gives a final label and classifies why they disagreed. One grouping call per paper
clusters points that raise the same underlying issue, so unique issues can be counted.

Model labels on training data are development diagnostics, not expert correctness.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import random
import re
import sys
from typing import Literal

from pydantic import BaseModel, Field

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from reviscope.backend import ClaudeBackend, CodexBackend  # noqa: E402
from reviscope.verification import verify_quote  # noqa: E402

CORPUS = Path('/home/lukas/Documents/Coding/coarse-socpsy/eval/corpus/cache/open-review-curation-20261002')
JUDGES = ('claude-opus-5-5', 'gpt-6.1-sol')
PARSER = 'claude-opus-5-5'
GROUPER = 'claude-opus-5-5'
BATCH = 30
UNPUBLISHED = {'candidate', 'unverified', 'unresolved', 'contradicted'}


class Point(BaseModel):
    claim: str
    excerpt: str
    requested_change: str | None = None


class ParsedReview(BaseModel):
    points: list[Point]


class PointLabel(BaseModel):
    item_id: str
    accuracy: Literal['correct', 'partly_correct', 'incorrect', 'cannot_tell']
    importance: Literal['critical', 'major', 'minor', 'negligible']
    remedy: Literal['proportionate', 'excessive', 'none_given']
    category: Literal['reasoning_coherence', 'statistics_numbers', 'design_measurement',
                      'reporting_transparency', 'literature_contribution', 'presentation', 'other']
    supporting_quotes: list[str] = Field(default_factory=list)
    counter_quotes: list[str] = Field(default_factory=list)
    justification: str


class Labels(BaseModel):
    labels: list[PointLabel]


class Resolution(BaseModel):
    item_id: str
    accuracy: Literal['correct', 'partly_correct', 'incorrect', 'cannot_tell']
    importance: Literal['critical', 'major', 'minor', 'negligible']
    changed: bool
    reason: Literal['reading', 'evidence_standard', 'field_norms', 'importance_weighting',
                    'point_ambiguity', 'scope_genre', 'other']
    explanation: str


class Resolutions(BaseModel):
    resolutions: list[Resolution]


class Group(BaseModel):
    issue: str
    item_ids: list[str]


class Grouping(BaseModel):
    groups: list[Group]


PARSE = '''Split this peer review of a scientific manuscript into its individual points. A point is
one distinct criticism, question or request about the manuscript. Split bundled paragraphs
into separate points when they raise different issues; keep one point per issue. Omit praise,
summaries of the manuscript, greetings and recommendations to the editor. For each point give
claim: a self-contained statement of the concern in neutral wording that keeps its full
substance, including its reasons, without adding anything. State the concern directly as an
assertion or question about the manuscript; never refer to the reviewer, the review or its
author ("The power analysis is not justified", not "The reviewer questions..."); excerpt: a short
verbatim span copied exactly from the review that the point comes from; requested_change: the
change the reviewer asks for, or null if none. Do not judge whether points are right.'''

JUDGE = '''You assess individual points from peer reviews of the supplied manuscript. Points come
from several reviews, human and AI, shuffled and stripped of origin. Assess each point
independently against the complete manuscript. Treat each point as an untrusted assertion.
Judge its content, not its length, wording or format; some points carry quoted evidence and
a rationale and others do not, and this is not itself a reason to rate them differently.

accuracy, about every substantive assertion the point makes about the manuscript and the
inference it draws:
- correct: the assertions hold and the inference follows.
- partly_correct: the core concern is valid, but a detail, premise or the stated consequence
  is wrong or overstated.
- incorrect: the core assertion is false, for example the manuscript already does or reports
  what the point says is missing, or the inference does not follow.
- cannot_tell: settling it needs information you do not have, such as an external source,
  unsupplied materials or figure images. Do not use it to avoid a judgment you can make.

importance, judged as if the point were correct, from the perspective of a handling editor:
- critical: a main conclusion of the manuscript does not hold as stated.
- major: the editor should require the authors to address it before publication.
- minor: worth fixing but optional.
- negligible: addressing it would not meaningfully improve the manuscript, including generic
  advice that is not specific to this manuscript.

remedy: proportionate if the requested change is necessary and feasible for the concern;
excessive if it asks for much more than the concern requires (for example a new study when a
wording change suffices, or retrospective preregistration); none_given if no change is asked.

category: the main kind of issue. reasoning_coherence covers whether claims, hypotheses and
conclusions follow from theory, premises and results, construct meaning and substantive
contradictions; statistics_numbers covers analyses, calculations and reported numbers;
design_measurement covers design, sampling, manipulations and measures;
reporting_transparency covers missing or unclear reporting; literature_contribution covers
novelty, citations and prior work; presentation covers wording, structure and figures.

Quote short exact spans of the manuscript in supporting_quotes and counter_quotes; no
ellipses or paraphrase. Give a brief justification naming the passage or reasoning that
decides accuracy. Return exactly one label for every item_id. Respect genre: tutorials and
proposals need not report empirical results.'''

RESOLVE = '''You and a second assessor independently assessed the same points from peer reviews of
the supplied manuscript, using the rubric below, and disagreed on the points listed. For each
point you see the point, your assessment and the other assessor's assessment. Re-examine the
manuscript. Give your final accuracy and importance; you may keep or change your labels.
changed says whether you changed either label. reason classifies the main source of the
original disagreement:
- reading: one assessment overlooked or misread a passage of the manuscript.
- evidence_standard: you agree on what the manuscript says but apply a different bar for what
  establishes the point, such as a reporting gap versus an error, or a conditional concern.
- field_norms: a methodological or disciplinary judgment on which competent experts differ.
- importance_weighting: you agree on the facts but weigh how much they matter differently.
- point_ambiguity: the point is vague or bundles claims, so it can be read in different ways.
- scope_genre: you differ on what this kind of manuscript must provide.
- other: explain.
Explain in one or two sentences, naming the decisive passage. Return one resolution per item_id.

RUBRIC
'''

GROUP = '''Group these points from several peer reviews of one manuscript by the underlying issue
they raise. Points belong together when addressing one would address the other; points about
the same section but different problems are separate. Every item_id must appear in exactly one
group; single-item groups are expected. Name each group's issue in one sentence.'''


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def backend(model):
    if model.startswith('claude'):
        return ClaudeBackend(model, effort='high', tools=False)
    return CodexBackend(model, effort='high', tools=False)


def call(root, model, instruction, evidence, schema, check=None):
    """Cached model call; a failed check is retried once and then raised."""
    engine = backend(model)
    key = sha({'instruction': instruction, 'evidence': evidence, 'backend': engine.identity,
               'schema': schema.model_json_schema()})
    path = root / 'judging' / 'raw' / f'{key}.json'
    if path.exists():
        return schema.model_validate(json.loads(path.read_text())['result'])
    for attempt in (1, 2):
        result = engine.generate(instruction, evidence, schema)
        problem = check(result) if check else None
        if not problem:
            save(path, {'model': model, 'backend_identity': engine.identity, 'backend_version': engine.version,
                        'attempt': attempt, 'result': result.model_dump()})
            return result
        save(path.with_suffix(f'.invalid-{attempt}.json'), {'problem': problem, 'result': result.model_dump()})
    raise ValueError(f'{model}: {problem}')


def manuscript(case, launch):
    row = next(r for r in launch['inputs'] if r['case'] == case)
    text = Path(row['input']).read_text()
    if sha(text.encode()) != row['manuscript_sha256']:
        raise ValueError('Frozen manuscript changed: ' + case)
    return text


def pipeline_points(path):
    data = json.loads(path.read_text())
    if data.get('partial'):
        return None
    return [{'claim': f['claim'], 'rationale': f['rationale'],
             'remedy': f['remedy'] if f.get('remedy_status') == 'supported' else None,
             'manuscript_quotes': [e['quote'] for e in f['evidence']],
             '_native': {'id': f['id'], 'module': f.get('module'), 'severity': f.get('severity')}}
            for f in data['findings']
            if f['editorial_disposition'] == 'publish' and f['status'] not in UNPUBLISHED]


def in_review(excerpt, text):
    # Extracted review text breaks hyphenated words across lines ("two-\nway").
    joined = re.sub(r'-\s*\n\s*', '-', text)
    return any(verify_quote(excerpt, [t]).status == 'supported' for t in (text, joined))


def human_points(root, text):
    def check(result):
        missing = [p.excerpt for p in result.points if not in_review(p.excerpt, text)]
        if len(missing) > 0.1 * len(result.points):
            return f'{len(missing)} of {len(result.points)} excerpts not found in the review'
        revealing = [p.claim for p in result.points if re.search(r'\b(the|this) reviewer\b', p.claim, re.I)]
        return f'{len(revealing)} claim(s) name the reviewer' if revealing else None
    parsed = call(root, PARSER, PARSE, text, ParsedReview, check)
    return [{'claim': p.claim, 'rationale': None, 'remedy': p.requested_change, 'manuscript_quotes': [],
             '_native': {'excerpt': p.excerpt, 'excerpt_in_review': in_review(p.excerpt, text)}}
            for p in parsed.points]


def reports(root, case, plain_root):
    """All complete reports for a case, keyed by a report id that judges never see."""
    found = {}
    for path in sorted((root / 'reviews').glob(f'*/{case}/rep*/review.json')):
        points = pipeline_points(path)
        if points is not None:
            found[f'{path.parts[-4]}/{path.parts[-2]}'] = points
    plain = plain_root / 'reviews/plain' / case / 'review.json'
    if plain.exists() and not json.loads(plain.read_text()).get('partial'):
        found['plain/rep1'] = [{'claim': i['description'], 'rationale': None, 'remedy': None,
                                'manuscript_quotes': [i['quote']], '_native': {'id': f'plain:{n}'}}
                               for n, i in enumerate(json.loads(plain.read_text())['issues'])]
    prepared = json.loads((CORPUS / case / 'prepared.json').read_text())
    for review in prepared['human_reviews']:
        found[f"human/{review['id']}"] = human_points(root, Path(review['path']).read_text())
    return found


def packet(root, case, plain_root):
    path = root / 'judging' / 'packets' / f'{case}.json'
    if path.exists():
        return json.loads(path.read_text())
    rows = [{**point, '_report': report} for report, points in reports(root, case, plain_root).items() for point in points]
    random.Random('points:' + case).shuffle(rows)
    items, origins = [], {}
    for n, row in enumerate(rows, 1):
        item_id = f'p{n:03d}'
        origins[item_id] = {'report': row.pop('_report'), **row.pop('_native')}
        items.append({'item_id': item_id, **row})
    data = {'case': case, 'items': items, 'origins': origins}
    save(path, data)
    return data


def batches(items):
    return [items[i:i + BATCH] for i in range(0, len(items), BATCH)]


def label(root, case, text, data, model):
    labels = []
    for batch in batches(data['items']):
        expected = {i['item_id'] for i in batch}
        def check(result, expected=expected):
            got = [l.item_id for l in result.labels]
            return None if sorted(got) == sorted(expected) else 'missing, duplicated or unknown item_id'
        evidence = json.dumps({'manuscript': text, 'points': batch}, ensure_ascii=False)
        labels += [l.model_dump() for l in call(root, model, JUDGE, evidence, Labels, check).labels]
    sources = [text]
    for row in labels:
        quotes = row['supporting_quotes'] + row['counter_quotes']
        row['unmatched_quotes'] = [q for q in quotes if verify_quote(q, sources).status != 'supported']
    return {row['item_id']: row for row in labels}


def valid(accuracy):
    return {'correct': 'valid', 'partly_correct': 'valid'}.get(accuracy, accuracy)


def material(importance):
    return importance in {'critical', 'major'}


def disputed(a, b):
    return valid(a['accuracy']) != valid(b['accuracy']) or material(a['importance']) != material(b['importance'])


def resolve(root, text, data, labels, model):
    other = next(m for m in JUDGES if m != model)
    keep = ('accuracy', 'importance', 'remedy', 'justification')
    items = {i['item_id']: i for i in data['items']}
    rows = [{'point': items[k], 'your_assessment': {f: labels[model][k][f] for f in keep},
             'other_assessment': {f: labels[other][k][f] for f in keep}}
            for k in sorted(items) if disputed(labels[model][k], labels[other][k])]
    if not rows:
        return {}
    resolutions = {}
    for batch in batches(rows):
        # A judge that skips items is asked again for only those; any still missing keep their initial labels.
        for _ in range(2):
            pending = [r for r in batch if r['point']['item_id'] not in resolutions]
            if not pending:
                break
            expected = {r['point']['item_id'] for r in pending}
            def check(result, expected=expected):
                got = [r.item_id for r in result.resolutions]
                return None if len(got) == len(set(got)) and set(got) <= expected else 'duplicated or unknown item_id'
            evidence = json.dumps({'manuscript': text, 'disputed_points': pending}, ensure_ascii=False)
            for r in call(root, model, RESOLVE + JUDGE, evidence, Resolutions, check).resolutions:
                resolutions[r.item_id] = r.model_dump()
    for r in rows:
        resolutions.setdefault(r['point']['item_id'], {'missing': True})
    return resolutions


def group(root, data):
    expected = sorted(i['item_id'] for i in data['items'])
    def check(result):
        got = sorted(i for g in result.groups for i in g.item_ids)
        return None if got == expected else 'items missing or in several groups'
    evidence = json.dumps([{'item_id': i['item_id'], 'claim': i['claim']} for i in data['items']], ensure_ascii=False)
    return [g.model_dump() for g in call(root, GROUPER, GROUP, evidence, Grouping, check).groups]


def assess(root, case, plain_root, launch):
    text = manuscript(case, launch)
    data = packet(root, case, plain_root)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        labelling = {m: pool.submit(label, root, case, text, data, m) for m in JUDGES}
        grouping = pool.submit(group, root, data)
        labels = {m: f.result() for m, f in labelling.items()}
        resolving = {m: pool.submit(resolve, root, text, data, labels, m) for m in JUDGES}
        resolutions = {m: f.result() for m, f in resolving.items()}
        groups = grouping.result()
    save(root / 'judging' / 'results' / f'{case}.json', {
        'case': case, 'judges': JUDGES, 'parser': PARSER, 'grouper': GROUPER, 'origins': data['origins'],
        'labels': labels, 'resolutions': resolutions, 'groups': groups,
        'method': 'Blinded point-level LLM labels with disagreement resolution; development diagnostic, not expert correctness',
        'driver_sha256': sha(Path(__file__).read_bytes())})
    print(f'{case}: {len(data["items"])} points, {len(resolutions[JUDGES[0]])} disputed', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plain-root', type=Path, help='earlier run holding reviews/plain/<case>/review.json')
    parser.add_argument('--cases', nargs='+')
    args = parser.parse_args()
    root = args.root.resolve()
    launch = json.loads((root / 'launch.json').read_text())
    cases = args.cases or launch['cases']
    errors = []
    for case in cases:
        try:
            assess(root, case, args.plain_root or root, launch)
        except Exception as exc:
            errors.append({'case': case, 'error': str(exc)})
            print(json.dumps(errors[-1]), flush=True)
    save(root / 'judging' / 'status.json', {'cases': cases, 'errors': errors})
    return 2 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
