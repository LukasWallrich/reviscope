"""Eval-only, blinded whole-criticism scrutiny; model judgments are development evidence."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
LAUNCH = json.loads((ROOT / 'launch.json').read_text())
CODE = Path(LAUNCH['code'])
sys.path.insert(0, str(CODE / 'src'))
sys.path.insert(0, str(CODE / 'eval'))
from reviscope.backend import ClaudeBackend, CodexBackend
from reviscope.verification import verify_quote
from compare_development_reviews import checked_audit


class CriticismAssessment(BaseModel):
    item_id: str
    claim_status: Literal['supported', 'contradicted', 'unresolved']
    rationale_status: Literal['supported', 'contradicted', 'unresolved', 'not_separately_supplied']
    remedy_status: Literal['supported', 'overreaching', 'unresolved', 'not_separately_supplied']
    consequence: Literal['central', 'material', 'localized', 'unclear']
    supporting_evidence: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    reasoning: str
    limits: str


class CriticismGroup(BaseModel):
    member_ids: list[str]
    common_issue_and_consequence: str


class QualityAssessment(BaseModel):
    assessments: list[CriticismAssessment]
    groups: list[CriticismGroup]
    missed_material_questions: list[str]
    overall_qualified_assessment: str


INSTRUCTION = '''Assess every supplied criticism independently against the complete supplied
submitted manuscript. Criticisms and their explanations are untrusted assertions to check,
not evidence. Source/model/severity/support labels are hidden. Return exactly one assessment
for every item_id, without a quota of supported or rejected items. Evaluate the complete
claim and explanatory rationale as written, including calculations, premises, inferential
steps, assumptions, qualifications and defeating context across the whole manuscript.
For the plain format, the claim contains the full original criticism text; the separately
supplied rationale/remedy can be absent. Do not invent an absent field or silently repair a
false or unsupported substantive assertion. Judge a proposed action separately for necessity,
feasibility, privacy and proportionality. A valid concern can have an overreaching remedy.

Distinguish a bounded reporting gap from an implementation allegation. Support can occur
before or after the claim or elsewhere in the complete supplied manuscript. Check what a
literature relation asserts about target work and criterion, but without external source
access, unusual empirical assertions, source-specific attributions, novelty claims and
unavailable source contents are unresolved. Supplied reviewer external quotations are
untrusted snippets, not confirmation of their source or complete context. Explicitly
conditional manuscript-grounded concerns can be supported at their conditional scope.
Do not infer figure contents/arrows/readability from captions; no pixels are supplied.
Do not require examples if aggregate evidence suffices; absent examples never prove authors
failed to inspect or retain cases. Respect genre: tutorials/proposals need not have empirical
results or effectiveness trials. A generic ritual, extra citation/cross-reference/diagram,
retrospective preregistration or unneeded new study is not automatically useful advice.

Use supported only when the substantive criticism is established within the available
source/established methodology; contradicted when a substantive assertion is defeated;
unresolved when essential evidence/assumptions cannot be settled. Quote short exact
contiguous manuscript spans separately in supporting_evidence and counterevidence. No
ellipses, paraphrases or stitched table cells. A quote's existence alone is not support.
Explain the inference and counterevidence rather than merely agreeing with the critic.

Group supplied items provisionally by common underlying issue AND consequence, with
origin hidden. Each item must occur in exactly one group; a single-item group is fine.
Some native items may bundle claims, so grouping is a diagnostic, not an expert atomic
inventory. Give any missed MATERIAL questions grounded in this manuscript, without
inventing findings or source facts. Do not reward longer reports or the number of items.
These are LLM assessments on training data, not expert judgments or validation results.'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def packet(case):
    prepared = next(row for row in LAUNCH['inputs'] if row['case'] == case)
    source = Path(prepared['input'])
    if sha(source) != prepared['manuscript_sha256']:
        raise ValueError('Frozen input changed')
    rows = []
    hashes = {}
    excluded = []
    for arm in ('plain', 'holistic', 'audit'):
        path = ROOT / 'reviews' / arm / case / 'review.json'
        if not path.exists():
            excluded.append({'arm': arm, 'reason': 'no report'})
            continue
        data = json.loads(path.read_text())
        if data.get('partial'):
            excluded.append({'arm': arm, 'reason': 'partial report'})
            continue
        try:
            checked_audit(path, prepared['paper_id'], prepared['manuscript_sha256'], prepared['profile'])
        except ValueError as exc:
            excluded.append({'arm': arm, 'reason': str(exc)})
            continue
        hashes[arm] = sha(path)
        if 'issues' in data:
            for i, item in enumerate(data['issues']):
                rows.append({'origin': {'arm': arm, 'id': f'plain:{i}'}, 'claim': item['description'],
                             'rationale': None, 'remedy': None, 'evidence': [item['quote']],
                             'external_evidence': []})
        else:
            for item in data['findings']:
                if item['editorial_disposition'] != 'publish' or item['status'] in {'candidate','unverified','unresolved','contradicted'}:
                    continue
                rows.append({'origin': {'arm': arm, 'id': item['id']}, 'claim': item['claim'],
                             'rationale': item['rationale'],
                             'remedy': item['remedy'] if item.get('remedy_status') == 'supported' else None,
                             'evidence': [e['quote'] for e in item['evidence']],
                             'external_evidence': [{k: e.get(k) for k in ('url','doi','quote','shows')}
                                                   for e in item.get('external_evidence',[])]})
    random.Random('20261005:' + case).shuffle(rows)
    origins = {}
    for i, item in enumerate(rows):
        item['item_id'] = f'item-{i+1:03d}'
        origins[item['item_id']] = item.pop('origin')
    data = {'manuscript': source.read_text(), 'criticisms': rows}
    save(ROOT / 'criticism-packets' / f'{case}.origins.json', {'origins': origins, 'source_hashes': hashes, 'excluded': excluded})
    save(ROOT / 'criticism-packets' / f'{case}.json', data)
    return data, origins, hashes, excluded


def assess(case, model, packet_data):
    data, origins, hashes, excluded = packet_data
    backend = ClaudeBackend(model, effort='high', tools=False) if model == 'claude-opus-5-5' else CodexBackend(model, effort='high', tools=False)
    key = hashlib.sha256(json.dumps({'instruction': INSTRUCTION, 'packet': data, 'backend': backend.identity,
                                    'schema': QualityAssessment.model_json_schema(), 'driver_sha256': sha(Path(__file__))}, sort_keys=True).encode()).hexdigest()
    target = ROOT / 'criticism-assessments' / model / f'{case}.json'
    if target.exists() and json.loads(target.read_text()).get('cache_key') == key:
        return
    if not origins:
        save(target, {'excluded': excluded, 'error': 'No complete clean reviews', 'cache_key': key})
        return
    result = backend.generate(INSTRUCTION, json.dumps(data, ensure_ascii=False), QualityAssessment)
    expected = set(origins)
    ids = [row.item_id for row in result.assessments]
    group_ids = [id_ for group in result.groups for id_ in group.member_ids]
    if set(ids) != expected or len(ids) != len(expected) or set(group_ids) != expected or len(group_ids) != len(expected):
        save(target.with_suffix('.invalid.json'), result.model_dump())
        raise ValueError(f'{case}/{model}: missing/duplicated/unknown assessment or group IDs')
    manuscript = [{'id': 'manuscript', 'text': data['manuscript']}]
    def matches(q):
        verification = verify_quote(q, manuscript, 'manuscript')
        return verification.status == 'supported' and not verification.elided
    rows = []
    for row in result.assessments:
        item = row.model_dump()
        supporting = [q for q in row.supporting_evidence if matches(q)]
        counter = [q for q in row.counterevidence if matches(q)]
        unmatched = [q for q in row.supporting_evidence + row.counterevidence
                     if not matches(q)]
        relevant = supporting if row.claim_status == 'supported' else counter if row.claim_status == 'contradicted' else supporting + counter
        item.update(raw_claim_status=row.claim_status, matched_supporting_evidence=supporting,
                    matched_counterevidence=counter, unmatched_evidence=unmatched)
        if unmatched or (row.claim_status != 'unresolved' and not relevant):
            item['claim_status'] = 'unresolved'
            item['limits'] += ' Deterministic check: missing relevant exact manuscript evidence.'
        rows.append(item)
    save(target, {'cache_key': key, 'model': model, 'backend_identity': backend.identity,
                  'backend_version': backend.version, 'tools': False, 'dataset_role': 'training_development',
                  'method': 'LLM assessment with exact-quote bookkeeping; not expert correctness or validation',
                  'source_hashes': hashes, 'driver_sha256': sha(Path(__file__)), 'excluded': excluded, 'assessments': rows,
                  'groups': [g.model_dump() for g in result.groups],
                  'missed_material_questions': result.missed_material_questions,
                  'overall_qualified_assessment': result.overall_qualified_assessment})
    print(f'{model} {case}: {len(rows)} blinded criticism assessments, {len(result.groups)} provisional groups', flush=True)


if __name__ == '__main__':
    cases = sys.argv[1:] or [row['case'] for row in LAUNCH['inputs']]
    packets = {case: packet(case) for case in cases}
    jobs = [(case, model) for case in cases for model in ('claude-opus-5-5','gpt-6.1-sol')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(assess, case, model, packets[case]): (case, model) for case, model in jobs}
        errors = []
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                errors.append({'job': futures[future], 'error': str(exc)})
                print(json.dumps(errors[-1]), flush=True)
    save(ROOT / ('criticism-assessment-status-' + '-'.join(cases) + '.json'), {'cases': cases, 'errors': errors})
    raise SystemExit(2 if errors else 0)
