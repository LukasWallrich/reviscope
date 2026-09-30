import json
import re

import pytest

from datetime import datetime, timezone

from reviscope.backend import Backend
from reviscope.discovery import TOPICS
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Profile, StudyMap, ToolCall

EXTERNAL = {'url': 'https://doi.org/10.1037/0033-2909.112.1.155', 'doi': None,
            'quote': 'A medium effect size is d = .50.', 'shows': 'The cited benchmark for a medium effect.'}


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
        if kind == 'DiscoveryResponse':
            blind = 'Perform one blind-spot audit' in instruction
            module = 'blind_spots' if blind else 'statistical_inference'
            rows = [{'check': key, 'status': 'assessed', 'rationale': 'Compared the reported sample flow.',
                     'evidence': [quote]} for key in TOPICS[module]]
            if self.bad_coverage:
                rows = rows[:1]
            if blind:
                self._tool_calls = [ToolCall(backend='test', sequence=0, kind='search', name='web_search',
                                             query='medium effect size benchmark', timestamp=datetime.now(timezone.utc))]
            return response_model.model_validate({
                'findings': [{'id': str(i), 'module': 'untrusted', 'claim': f'{module} issue {i}',
                              'rationale': 'Specific consequence', 'remedy': 'Check denominator',
                              'evidence': [quote], 'external_evidence': [EXTERNAL] if blind else []}
                             for i in range(1 if blind else 6)],
                'checks': rows, 'search_incomplete': False,
            })
        if kind == 'VerificationResponse':
            candidates = json.loads(instruction.split('CANDIDATES\n')[1].split('\nDISCIPLINE RULES')[0])
            return response_model.model_validate({'decisions': [{
                'finding_id': c['finding_id'], 'status': 'supported', 'rationale': 'Checked',
                'evidence': c['quoted_evidence'], 'external_evidence': c['external_evidence'],
                'remedy_status': 'supported', 'remedy_rationale': 'Small fix',
            } for c in candidates]})
        if kind == 'EditorialResponse':
            findings = json.loads(instruction.split('FINDINGS\n')[1])
            return response_model.model_validate({'decisions': [{
                'finding_id': row['id'], 'disposition': 'keep', 'reason': 'Distinct', 'target_id': None,
            } for row in findings], 'reconciled_overview': {
                'design_summary': 'd', 'contribution_summary': 'c', 'strengths': [],
            }})
        raise AssertionError(kind)


def test_discovery_blind_spot_external_evidence_tool_provenance_and_cache(tmp_path):
    paper = tmp_path / 'paper.txt'
    paper.write_text('24 of 60 people withdrew. ' + 'Study context. ' * 100)
    profile = Profile(id='deep-test', title='test', modules=['statistical_inference'],
                      module_prompts={'statistical_inference': 'Review statistics.'},
                      metadata={'coverage_first': True})
    backend = DiscoveryBackend()
    pipeline = ReviewPipeline(backend, profile, max_findings=7)
    run = pipeline.run(paper, output_dir=tmp_path / 'run')
    assert not run.partial
    assert len(run.candidates) == 7
    assert len(backend.calls) == 5
    blind = next(c for c in backend.calls if 'Perform one blind-spot audit' in c[1])
    assert 'statistical_inference issue 5' in blind[2] and 'COVERAGE LEDGER' in blind[2]
    assert any('numerical_and_power_claims: assessed' in row for row in run.coverage)
    published = next(f for f in run.findings if f.module == 'blind_spots')
    assert published.editorial_disposition == 'publish' and published.status == 'llm_supported'
    assert published.external_evidence[0].url == EXTERNAL['url']
    markdown = (tmp_path / 'run/review.md').read_text()
    assert 'External source: “A medium effect size is d = .50.”' in markdown and EXTERNAL['url'] in markdown
    assert '1 tool calls: 1 search' in markdown and '“medium effect size benchmark”' in markdown
    count = len(backend.calls)
    rerun = pipeline.run(paper, output_dir=tmp_path / 'run')
    assert len(backend.calls) == count
    cached = next(s for s in rerun.stages if s.name == 'review-blind_spots')
    assert cached.status == 'cached' and cached.tool_calls[0].stage == 'review-blind_spots'


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
