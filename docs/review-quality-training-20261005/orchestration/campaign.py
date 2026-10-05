"""Local, reproducible training assessment orchestration; all calls use subscription CLIs."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CORPUS = Path('/home/lukas/Documents/Coding/coarse-socpsy/eval/corpus/cache/open-review-curation-20261002')
PYTHON = '/home/lukas/Documents/Coding/coarse-socpsy/.venv/bin/python'
LOCK = threading.Lock()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def event(data):
    with LOCK:
        with (ROOT / 'events.jsonl').open('a') as handle:
            handle.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **data}) + '\n')
        print(json.dumps(data), flush=True)


def execute(command, log, code):
    env = {k: v for k, v in os.environ.items() if k not in
           {'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'OPENAI_API_KEY'}}
    env['PYTHONPATH'] = str(code / 'src')
    started = time.monotonic()
    with log.open('a') as handle:
        handle.write(json.dumps(command) + '\n'); handle.flush()
        outcome = subprocess.run(command, cwd=code, env=env, stdout=handle, stderr=subprocess.STDOUT)
    return {'command': command, 'returncode': outcome.returncode, 'seconds': time.monotonic() - started}


def audit(case, arm, code):
    path = ROOT / 'reviews' / arm / case / 'review.json'
    return execute([PYTHON, str(code / 'eval/audit_tool_use.py'), str(path), '--json',
                    str(path.parent / 'tool-audit.json')], ROOT / f'audit-{arm}-{case}.log', code)


def generation(job, code):
    case, mode, profile = job
    source = ROOT / 'inputs' / case / 'manuscript.txt'
    log = ROOT / f'{mode}-{case}.log'
    results = []
    event({'case': case, 'mode': mode, 'state': 'started', 'profile': profile})
    for attempt in range(2):
        if mode == 'plain':
            target = ROOT / 'reviews/plain' / case / 'review.json'
            command = [PYTHON, str(code / 'eval/plain_review.py'), str(source), '--model', 'gpt-6.1-sol',
                       '--effort', 'high', '--no-category-list', '--output', str(target)]
            if target.exists() and not json.loads(target.read_text()).get('partial'):
                break
        else:
            command = [PYTHON, str(code / 'eval/run_development_review.py'), str(source),
                       '--root', str(ROOT), '--case', case, '--profile', profile]
        result = execute(command, log, code)
        result.update(attempt=attempt + 1, mode=mode, case=case, profile=profile)
        results.append(result)
        targets = [ROOT / 'reviews' / arm / case / 'review.json' for arm in
                   (['plain'] if mode == 'plain' else ['holistic', 'audit'])]
        if all(p.exists() and not json.loads(p.read_text()).get('partial') for p in targets):
            break
        event({'case': case, 'mode': mode, 'state': 'retry_partial', 'attempt': attempt + 1})
        for p in targets:
            if p.exists() and json.loads(p.read_text()).get('partial'):
                (p.parent / f'review.partial-attempt-{attempt+1}.json').write_bytes(p.read_bytes())
    audits = []
    for arm in (['plain'] if mode == 'plain' else ['holistic', 'audit']):
        p = ROOT / 'reviews' / arm / case / 'review.json'
        if p.exists():
            audits.append({'arm': arm, **audit(case, arm, code)})
    save(ROOT / 'generation' / f'{mode}-{case}.json', {'attempts': results, 'audits': audits})
    event({'case': case, 'mode': mode, 'state': 'finished', 'attempts': len(results)})
    return results


def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--prepare':
        print('Preparation occurs after local-main integration; run without --prepare to execute.')
        return
    # Immutable code, reviewer-only input copies and explicit provenance precede every model call.
    namespace = runpy.run_path(str(REPO / 'eval/run_known_errors.py'))
    code, digest = namespace['snapshot'](ROOT)
    manifest = json.loads((code / 'eval/corpus/open_peer_review_curated.v1.json').read_text())
    entries = manifest['entries']
    jobs = []
    inputs = []
    for entry in entries:
        case = entry['cache_key']
        prepared = json.loads((CORPUS / case / 'prepared.json').read_text())
        source = Path(prepared['manuscript_text'])
        content = source.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != prepared['manuscript_text_sha256'] or actual != entry['manuscript_text_sha256']:
            raise ValueError('Input changed: ' + case)
        destination = ROOT / 'inputs' / case / 'manuscript.txt'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != content:
            raise ValueError('Frozen reviewer input differs: ' + case)
        destination.write_bytes(content)
        inputs.append({'case': case, 'paper_id': prepared['paper_id'], 'profile': prepared['profile'],
                       'manuscript_sha256': actual, 'input': str(destination), 'dataset_role': 'training_development'})
        jobs.extend([(case, 'plain', prepared['profile']), (case, 'pipeline', prepared['profile'])])
    save(ROOT / 'launch.json', {'code': str(code), 'code_sha256': digest,
         'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
         'authentication': 'ChatGPT and Claude Max subscription; API-key variables removed',
         'dataset_role': 'training_development', 'replicates': 1, 'inputs': inputs,
         'versions': {name: subprocess.check_output([name, '--version'],text=True).strip() for name in ['codex','claude']},
         'driver_sha256': sha(Path(__file__)), 'workers': 4})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(generation, job, code): job for job in jobs}
        failures = []
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                failures.append({'job': futures[future], 'error': str(exc)})
                event({'job': futures[future], 'state': 'failed', 'error': str(exc)})
    save(ROOT / 'generation-complete.json', {'failures': failures})
    event({'state': 'generation_complete', 'failures': failures})


if __name__ == '__main__':
    main()
