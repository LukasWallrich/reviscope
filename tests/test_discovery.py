import json
import re

import pytest

from reviscope.backend import Backend
from reviscope.discovery import (
    CalculationPlan, calculate, execute_plan, TOPICS,
)
from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Profile, StudyMap


@pytest.mark.parametrize('expression', [
    '__import__("os").system("id")', 'open("secret")', '(1).__class__',
    '[x for x in range(100)]', '2**100000', 'sqrt(-1)', '1/0',
    'normal_ppf(1)', 't_p(2, 30, 7)', 'rm_n(.1,2,2,.07,.05,1,2)',
])
def test_calculator_rejects_code_and_invalid_requests(expression):
    with pytest.raises((ValueError, TypeError, ArithmeticError)):
        calculate(expression)


def test_calculator_reproduces_known_numerical_results():
    assert calculate('100 * 24 / 60') == 40
    assert calculate('t_p(2.0422724563,30,2)') == pytest.approx(.05)
    assert calculate('f_p(4.1708767858,1,30)') == pytest.approx(.05)
    assert calculate('rm_n(.1,4,2,.07,.05,1,.9)') == 664
    assert calculate('rm_n(.25,2,2,.07,.05,1,.9)') == 82
    assert calculate('rm_power(82,.25,2,2,.07,.05,1)') == pytest.approx(.9065475722)


def test_unanchored_calculation_is_not_executed(tmp_path):
    paper = tmp_path / 'paper.txt'
    paper.write_text('We enrolled 60 people, of whom 24 withdrew.')
    source = ingest(paper)
    plan = CalculationPlan.model_validate({'requests': [{
        'id': 'one', 'question': 'Attrition percentage', 'expression': '24/60*100',
        'assumptions': 'Baseline denominator',
        'evidence': [{'source_id': source.id, 'quote': 'We enrolled 100 people.'}],
    }], 'not_checkable': []})
    result = execute_plan(plan, [source]).results[0]
    assert result.status == 'unavailable' and result.value is None


class DiscoveryBackend(Backend):
    name, model, effort = 'discovery-test', 'test', 'high'

    def __init__(self, bad_coverage=False):
        self.calls = []
        self.bad_coverage = bad_coverage

    def generate(self, instruction, evidence, response_model):
        self.calls.append((response_model.__name__, instruction, evidence))
        kind = response_model.__name__
        if kind == 'StudyMap':
            return StudyMap(studies=[], research_question='q', design_summary='d',
                            contribution_summary='c', strengths=[])
        source_id = re.search(r'SOURCE_ID:\s*(\S+)', evidence)
        quote = {'source_id': source_id.group(1), 'quote': '24 of 60 people withdrew.'} if source_id else None
        if kind == 'CalculationPlan':
            return response_model.model_validate({'requests': [{
                'id': 'flow', 'question': 'Attrition percentage', 'expression': '24/60*100',
                'assumptions': 'Enrolled denominator', 'evidence': [quote],
            }], 'not_checkable': []})
        if kind == 'DiscoveryResponse':
            blind = 'Perform one blind-spot audit' in instruction
            module = 'blind_spots' if blind else 'statistical_inference'
            rows = [{'check': key, 'status': 'assessed', 'rationale': 'Compared the reported sample flow.',
                     'evidence': [quote]} for key in TOPICS[module]]
            if self.bad_coverage:
                rows = rows[:1]
            return response_model.model_validate({
                'findings': [{'id': str(i), 'module': 'untrusted', 'claim': f'{module} issue {i}',
                              'rationale': 'Specific consequence', 'remedy': 'Check denominator',
                              'evidence': [quote]} for i in range(1 if blind else 6)],
                'checks': rows, 'search_incomplete': False,
                'deferred_tool_checks': [{
                    'question': 'Would the exclusion sensitivity change the inference?',
                    'capability': 'data_analysis',
                    'proposed_action': 'Fit the stated model with and without the specified exclusions.',
                    'required_inputs': ['Missing: participant-level data; available: reported sample flow'],
                    'expected_review_impact': 'Robustness would reduce the concern; a reversal would strengthen it.',
                    'stopping_rule': 'Stop after comparing the two prespecified estimates and intervals.',
                    'priority': 'high', 'evidence': [quote],
                    'module': 'forged', 'anchor_status': 'anchored',
                }] if blind else [],
            })
        if kind == 'VerificationResponse':
            assert 'BOUNDED CALCULATIONS' in evidence
            candidates = json.loads(instruction.split('CANDIDATES\n')[1].split('\nDISCIPLINE RULES')[0])
            return response_model.model_validate({'decisions': [{
                'finding_id': c['finding_id'], 'status': 'supported', 'rationale': 'Checked',
                'evidence': c['quoted_evidence'], 'remedy_status': 'supported', 'remedy_rationale': 'Small fix',
            } for c in candidates]})
        if kind == 'EditorialResponse':
            findings = json.loads(instruction.split('FINDINGS\n')[1])
            return response_model.model_validate({'decisions': [{
                'finding_id': row['id'], 'disposition': 'keep', 'reason': 'Distinct', 'target_id': None,
            } for row in findings], 'reconciled_overview': {
                'design_summary': 'd', 'contribution_summary': 'c', 'strengths': [],
            }})
        raise AssertionError(kind)


def test_discovery_six_findings_blind_spot_calculation_verification_and_cache(tmp_path):
    paper = tmp_path / 'paper.txt'
    paper.write_text('24 of 60 people withdrew. ' + 'Study context. ' * 100)
    profile = Profile(id='deep-test', title='test', modules=['statistical_inference'],
                      module_prompts={'statistical_inference': 'Review statistics.'},
                      metadata={'coverage_first': True})
    backend = DiscoveryBackend()
    pipeline = ReviewPipeline(backend, profile, max_findings=3)
    run = pipeline.run(paper, output_dir=tmp_path / 'run')
    assert not run.partial
    assert len(run.candidates) == 7
    assert len(run.deferred_tool_checks) == 1
    deferred = run.deferred_tool_checks[0]
    assert deferred.module == 'blind_spots' and deferred.anchor_status == 'anchored'
    assert len(backend.calls) == 6  # telemetry creates no additional tool/model calls
    persisted = json.loads((tmp_path / 'run/review.json').read_text())
    assert persisted['deferred_tool_checks'][0]['question'] == deferred.question
    markdown = (tmp_path / 'run/review.md').read_text()
    assert 'Deferred tool checks — not executed' in markdown
    assert 'not manuscript findings' in markdown
    from reviscope.evaluation import read_review, strip_review_metadata
    assert deferred.question not in read_review(tmp_path / 'run/review.json')
    assert deferred.question not in strip_review_metadata(markdown)
    assert sum(f.editorial_disposition == 'publish' for f in run.findings) == 3
    blind = next(c for c in backend.calls if 'Perform one blind-spot audit' in c[1])
    assert 'statistical_inference issue 5' in blind[2]
    assert 'COVERAGE LEDGER' in blind[2] and '40.0' in blind[2]
    assert any('numerical_and_power_claims: assessed' in row for row in run.coverage)
    count = len(backend.calls)
    pipeline.run(paper, output_dir=tmp_path / 'run')
    assert len(backend.calls) == count


def test_omitted_coverage_retains_findings_but_marks_search_incomplete(tmp_path):
    paper = tmp_path / 'paper.txt'
    paper.write_text('24 of 60 people withdrew. ' + 'Context. ' * 200)
    profile = Profile(id='deep-test', title='test', modules=['statistical_inference'],
                      module_prompts={'statistical_inference': 'Review.'}, metadata={'coverage_first': True})
    run = ReviewPipeline(DiscoveryBackend(bad_coverage=True), profile).run(paper, output_dir=tmp_path / 'run')
    assert run.partial
    assert next(s for s in run.stages if s.name == 'review-statistical_inference').status == 'completed'
    assert len(run.candidates) == 7
    assert any('not_checked' in row for row in run.coverage)
    raw_path = next((tmp_path / 'run/raw-discovery').glob('statistical_inference-*.json'))
    raw = json.loads(raw_path.read_text())
    assert len(raw['checks']) == 1 and len(raw['findings']) == 6


def test_deferred_check_cannot_forge_source_anchor_status(tmp_path):
    class UnanchoredProposalBackend(DiscoveryBackend):
        def generate(self, instruction, evidence, response_model):
            value = super().generate(instruction, evidence, response_model)
            if response_model.__name__ == 'DiscoveryResponse':
                for check in value.deferred_tool_checks:
                    check.evidence[0].quote = 'This sentence is absent from the source.'
                    check.anchor_status = 'anchored'
            return value

    paper = tmp_path / 'paper.txt'
    paper.write_text('24 of 60 people withdrew. ' + 'Context. ' * 200)
    profile = Profile(id='deep-test', title='test', modules=['statistical_inference'],
                      module_prompts={'statistical_inference': 'Review.'}, metadata={'coverage_first': True})
    run = ReviewPipeline(UnanchoredProposalBackend(), profile).run(paper, output_dir=tmp_path / 'run')
    assert not run.partial
    assert run.deferred_tool_checks[0].anchor_status == 'unanchored'
    assert len(run.candidates) == 7  # requests never become findings


def test_partial_adjudication_requires_explicit_diagnostic_opt_in(tmp_path):
    import csv
    import runpy
    from pathlib import Path
    from reviscope.schemas import ReviewRun, RunMetadata

    load_inputs = runpy.run_path(str(Path(__file__).parents[1] / 'eval/adjudicate_known_errors.py'))['load_inputs']
    run = ReviewRun(metadata=RunMetadata(run_id='test', backend='fixture', profile='test',
                                        profile_hash='x', input_hash='x', output_dir=str(tmp_path)),
                    sources=[], partial=True)
    review = tmp_path / 'review.json'
    review.write_text(run.model_dump_json())
    labels = tmp_path / 'annotations.csv'
    with pytest.raises(ValueError, match='partial'):
        load_inputs(review, labels, '7')  # rejects before opening held-out labels
    with labels.open('w') as handle:
        fields = ['paper', 'category', 'subcategory', 'original_snippet', 'modified_snippet', 'description']
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for _ in range(10):
            writer.writerow({key: '7' if key == 'paper' else 'test' for key in fields})
    loaded, errors, _, _ = load_inputs(review, labels, '7', allow_partial=True)
    assert loaded.partial and len(errors) == 10
