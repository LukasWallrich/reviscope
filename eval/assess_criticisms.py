"""Eval-only, blinded whole-criticism scrutiny; model judgments are development evidence."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from typing import Literal

from pydantic import BaseModel, Field

ROOT: Path
LAUNCH: dict
from reviscope.backend import ClaudeBackend, CodexBackend
from reviscope.verification import verify_quote
from reviscope.render import unconfirmed_concerns
from reviscope.schemas import ReviewRun
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


INSTRUCTION = '''Assess every supplied unique criticism against the complete supplied
submitted manuscript. Criticisms and their explanations are untrusted assertions to check,
not evidence. Source/model/severity/support labels are hidden. Identical complete items inherited
by both nested arms are supplied once. This is a pooled call, not independent calls;
evaluate each item separately rather than treating another criticism as evidence. Return exactly one assessment
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


def deduplicate_items(rows):
    """Share identical full presentations across arms, retaining every native origin."""
    unique = {}
    for original in rows:
        row = dict(original)
        origin = row.pop('origin')
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in unique:
            unique[key] = {**row, '_origins': []}
        unique[key]['_origins'].append(origin)
    return list(unique.values())


def packet(case):
    prepared = next(row for row in LAUNCH['inputs'] if row['case'] == case)
    source = Path(prepared['input'])
    if sha(source) != prepared['manuscript_sha256']:
        raise ValueError('Frozen input changed')
    rows = []
    hashes = {}
    excluded = []
    unconfirmed = {}
    arm_ids = {}
    arm_findings = {}
    legacy_remedies = {}
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
        if 'issues' not in data:
            try:
                parsed = ReviewRun.model_validate(data)
            except ValueError as exc:
                excluded.append({'arm': arm, 'reason': 'Current schema/renderer validation failed: ' + str(exc)})
                continue
            unconfirmed[arm] = [f.id for f in unconfirmed_concerns(parsed)]
            arm_findings[arm] = {f['id']: f for f in data['findings']}
            arm_ids[arm] = [f['id'] for f in data['findings'] if f['editorial_disposition']=='publish' and f['status'] not in {'candidate','unverified','unresolved','contradicted'}]
        if arm in arm_ids:
            legacy_remedies[arm] = [i for i in arm_ids[arm] if arm_findings[arm][i].get('remedy_status') is None]
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
    rows = deduplicate_items(rows)
    random.Random('20261005:' + case).shuffle(rows)
    origins = {}
    for i, item in enumerate(rows):
        item['item_id'] = f'item-{i+1:03d}'
        origins[item['item_id']] = item.pop('_origins')
    data = {'manuscript': source.read_text(), 'criticisms': rows}
    nested_included = all(arm in hashes for arm in ('holistic', 'audit'))
    not_published = [] if nested_included else None
    if nested_included:
        for id_ in sorted(set(arm_ids['holistic']) - set(arm_ids['audit'])):
            item = arm_findings['audit'].get(id_, {})
            not_published.append({'id': id_, 'present_in_audit': id_ in arm_findings['audit'], 'audit_status': item.get('status'),
                                  'audit_disposition': item.get('editorial_disposition'),
                                  'audit_reason': item.get('editorial_reason') or item.get('verification'),
                                  'merge_target': item.get('merged_into')})
    by_native_id = {}
    for item_id, native_origins in origins.items():
        for origin in native_origins:
            by_native_id.setdefault(origin['id'], []).append((item_id, origin['arm']))
    unmerged = {id_: rows for id_, rows in by_native_id.items()
                if len({i for i, arm in rows}) > 1 and {'holistic', 'audit'} <= {arm for i, arm in rows}}
    import reviscope.render as render_policy
    provenance = {'origins': origins, 'render_policy_sha256': sha(Path(render_policy.__file__)),
                  'review_schema_sha256': hashlib.sha256(json.dumps(ReviewRun.model_json_schema(), sort_keys=True).encode()).hexdigest(), 'source_hashes': hashes, 'excluded': excluded,
                  'unconfirmed_author_visible_excluded': unconfirmed,
                  'nested_arm_finding_ids': arm_ids,
                  'holistic_not_published_in_audit': not_published,
                  'nested_comparison_unavailable_reason': None if nested_included else 'Both nested arms were not included; exclusions are not editorial losses',
                  'same_id_unmerged_presentations': unmerged, 'legacy_unassessed_remedies': legacy_remedies,
                  'audit_inherited_ids': [i for i in arm_ids.get('audit', []) if i.startswith('broad:')] if nested_included else None,
                  'audit_new_ids': [i for i in arm_ids.get('audit', []) if i.startswith('evidence_audit:')] if nested_included else None,
                  'n_native_items': sum(len(x) for x in origins.values()), 'n_unique_presentations': len(rows)}
    for path in (ROOT / 'criticism-packets-v2' / f'{case}.origins.json', ROOT / 'criticism-packets-v2' / f'{case}.json'):
        archive(path)
    save(ROOT / 'criticism-packets-v2' / f'{case}.origins.json', provenance)
    save(ROOT / 'criticism-packets-v2' / f'{case}.json', data)
    active_packet = ROOT / 'criticism-packets-v2' / f'{case}.json'
    snapshot = active_packet.parent / 'history' / (case + '-' + sha(active_packet) + '.json')
    if not snapshot.exists():
        snapshot.parent.mkdir(exist_ok=True)
        snapshot.write_bytes(active_packet.read_bytes())
    return data, origins, hashes, excluded


def checked_labels(row, manuscript_text):
    """Quote bookkeeping only; retain the judge's labels and matched spans."""
    item = dict(row)
    item['original_limits'] = row.get('original_limits', row.get('limits', ''))
    raw = row.get('raw_claim_status', row['claim_status'])
    manuscript = [{'id': 'manuscript', 'text': manuscript_text}]
    def matches(q):
        verification = verify_quote(q, manuscript, 'manuscript')
        return verification.status == 'supported' and not verification.elided
    supporting = [q for q in row['supporting_evidence'] if matches(q)]
    counter = [q for q in row['counterevidence'] if matches(q)]
    unmatched = [q for q in row['supporting_evidence'] + row['counterevidence'] if not matches(q)]
    relevant = supporting if raw == 'supported' else counter if raw == 'contradicted' else supporting + counter
    checked = 'unresolved' if unmatched or (raw != 'unresolved' and not relevant) else raw
    item.update(raw_claim_status=raw, claim_status=checked, matched_supporting_evidence=supporting,
                matched_counterevidence=counter, unmatched_evidence=unmatched,
                quote_check_only_disagreement=checked != raw,
                quote_check_passed=not unmatched and (raw == 'unresolved' or bool(relevant)))
    if item['quote_check_passed'] and 'limits' in item:
        item['limits'] = item['limits'].replace(' Deterministic check: missing relevant exact manuscript evidence.', '')
    return item


def require_repaired_matcher(launch):
    import reviscope.verification as verification
    if verify_quote('p = .88', ['p = .88.']).status != 'supported':
        raise ValueError('Assessment requires the repaired numeric quote matcher; check PYTHONPATH')
    module = Path(verification.__file__).resolve()
    if module.is_relative_to(Path(launch['code']).resolve()):
        raise ValueError('Refusing the original frozen generation matcher in the repaired assessment')
    return str(module)


def method_hash():
    import reviscope.verification as verification
    # Changed numeric anchoring must never reuse stale derived judgments.
    return hashlib.sha256((sha(Path(__file__)) + sha(Path(verification.__file__))).encode()).hexdigest()


def archive(path):
    if path.exists():
        history = path.parent / 'history' / (path.stem + '-' + sha(path) + path.suffix)
        if not history.exists():
            history.parent.mkdir(parents=True, exist_ok=True)
            history.write_bytes(path.read_bytes())


def assess(case, model, packet_data, *, offline=False):
    data, origins, hashes, excluded = packet_data
    backend = ClaudeBackend(model, effort='high', tools=False) if model == 'claude-opus-5-5' else CodexBackend(model, effort='high', tools=False)
    matcher_module = require_repaired_matcher(LAUNCH)
    packet_path = ROOT / 'criticism-packets-v2' / f'{case}.json'
    if json.loads(packet_path.read_text()) != data:
        raise ValueError('Packet on disk differs from the judge input')
    packet_digest = sha(packet_path)
    # Raw calls depend only on judge inputs/settings. Matcher repairs rederive
    # labels from retained raw calls without introducing new model sampling.
    key = hashlib.sha256(json.dumps({'instruction': INSTRUCTION, 'packet': data, 'backend': backend.identity,
                                    'schema': QualityAssessment.model_json_schema(), 'protocol': 'unique-criticism-v2'}, sort_keys=True).encode()).hexdigest()
    target = ROOT / 'criticism-assessments-v2' / model / f'{case}.json'
    if not origins:
        archive(target)
        save(target, {'excluded': excluded, 'error': 'No complete clean reviews', 'cache_key': key})
        return
    raw_path = ROOT / 'criticism-judge-raw-v2' / model / case / (key + '.json')
    if raw_path.exists():
        result = QualityAssessment.model_validate(json.loads(raw_path.read_text())['result'])
        call_metadata = json.loads(raw_path.read_text())['call_metadata']
    else:
        if offline:
            raise ValueError('Offline rederivation requires an existing matching valid raw judge cache; no model call made')
        result = backend.generate(INSTRUCTION, json.dumps(data, ensure_ascii=False), QualityAssessment)
        call_metadata = {'backend_identity': backend.identity, 'backend_version': backend.version, 'tools': False}
    expected = set(origins)
    ids = [row.item_id for row in result.assessments]
    group_ids = [id_ for group in result.groups for id_ in group.member_ids]
    if set(ids) != expected or len(ids) != len(expected) or set(group_ids) != expected or len(group_ids) != len(expected):
        invalid = target.with_suffix('.invalid.json')
        archive(invalid)
        save(invalid, result.model_dump())
        raise ValueError(f'{case}/{model}: missing/duplicated/unknown assessment or group IDs')
    if not raw_path.exists():
        save(raw_path, {'cache_key': key, 'result': result.model_dump(), 'call_metadata': call_metadata,
                        'packet_sha256': packet_digest, 'protocol': 'unique-criticism-v2'})
    rows = [checked_labels(row.model_dump(), data['manuscript']) for row in result.assessments]
    packet_path = ROOT / 'criticism-packets-v2' / f'{case}.json'
    if json.loads(packet_path.read_text()) != data or sha(packet_path) != packet_digest:
        raise ValueError('Packet changed during assessment')
    packet_snapshot = packet_path.parent / 'history' / (case + '-' + packet_digest + '.json')
    provenance = json.loads((packet_path.with_suffix('.origins.json')).read_text())
    archive(target)
    save(target, {'cache_key': key, 'model': model, 'backend_identity': backend.identity,
                  'backend_version': call_metadata['backend_version'], 'tools': False, 'dataset_role': 'training_development',
                  'method': 'LLM assessment with exact-quote bookkeeping; not expert correctness or validation',
                  'source_hashes': hashes, 'method_sha256': method_hash(),
                  'matcher_module': matcher_module,
                  'packet_sha256': packet_digest, 'packet_snapshot': str(packet_snapshot),
                  'origins': origins, 'packet_provenance': provenance,
                  'raw_judge_artifact': str(raw_path), 'raw_judge_sha256': sha(raw_path), 'excluded': excluded, 'assessments': rows,
                  'groups': [g.model_dump() for g in result.groups],
                  'missed_material_questions': result.missed_material_questions,
                  'overall_qualified_assessment': result.overall_qualified_assessment})
    print(f'{model} {case}: {len(rows)} blinded criticism assessments, {len(result.groups)} provisional groups', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--offline', action='store_true', help='Rewrap matching raw calls only; refuse any new model call')
    args = parser.parse_args()
    ROOT = args.root.resolve()
    LAUNCH = json.loads((ROOT / 'launch.json').read_text())
    cases = args.cases or [row['case'] for row in LAUNCH['inputs']]
    packets = {case: packet(case) for case in cases}
    jobs = [(case, model) for case in cases for model in ('claude-opus-5-5','gpt-6.1-sol')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(assess, case, model, packets[case], offline=args.offline): (case, model) for case, model in jobs}
        errors = []
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                errors.append({'job': futures[future], 'error': str(exc)})
                print(json.dumps(errors[-1]), flush=True)
    save(ROOT / ('criticism-assessment-v2-status-' + '-'.join(cases) + '.json'), {'cases': cases, 'errors': errors})
    raise SystemExit(2 if errors else 0)
