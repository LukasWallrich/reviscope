"""Wait for bound clean generation, then assess frozen reports through subscription CLIs."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parent
LAUNCH=json.loads((ROOT/'launch.json').read_text())
CODE=Path(LAUNCH['code'])
PYTHON='/home/lukas/Documents/Coding/coarse-socpsy/.venv/bin/python'
CORPUS='/home/lukas/Documents/Coding/coarse-socpsy/eval/corpus/cache/open-review-curation-20261002'
ENV={k:v for k,v in os.environ.items() if k not in {'ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','OPENAI_API_KEY'}}
ENV['PYTHONPATH']=str(CODE/'src')

def execute(command):
    with (ROOT/'assessment.log').open('a') as log:
        log.write(json.dumps({'at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'command':command})+'\n'); log.flush()
        result=subprocess.run(command,cwd=CODE,env=ENV,stdout=log,stderr=subprocess.STDOUT)
    return {'command':command,'returncode':result.returncode}

pending=[row['case'] for row in LAUNCH['inputs']]
results=[]
early_done=set()
while pending:
    ready=[case for case in pending if all((ROOT/'generation'/f'{mode}-{case}.json').exists() for mode in ['plain','pipeline'])]
    if not ready:
        early=[case for case in pending if case not in early_done
               and (ROOT/'generation'/f'plain-{case}.json').exists()
               and (ROOT/'reviews/holistic'/case/'review.json').exists()]
        if early:
            case=early[0]
            report=ROOT/'reviews/holistic'/case/'review.json'
            results.append(execute([PYTHON,str(CODE/'eval/audit_tool_use.py'),str(report),'--json',str(report.parent/'tool-audit.json')]))
            base=[PYTHON,str(CODE/'eval/compare_development_reviews.py'),'--root',str(ROOT),'--corpus',CORPUS,'--cases',case,'--workers','2','--arms','plain','holistic','--ai-only']
            for model in ['claude-opus-5-5','gpt-6.1-sol']:
                results.append(execute(base+['--model',model]))
            early_done.add(case)
            (ROOT/'assessment-progress.json').write_text(json.dumps({'results':results,'pending':pending,'early_done':sorted(early_done)},indent=2)+'\n')
            continue
        if (ROOT/'generation-complete.json').exists():
            results.append({'unavailable':pending}); break
        time.sleep(20); continue
    case=ready[0]
    results.append(execute([PYTHON,str(ROOT/'criticism_audit.py'),case]))
    # Source-audit checks and exact submitted-version checks execute before any comparison call.
    base=[PYTHON,str(CODE/'eval/compare_development_reviews.py'),'--root',str(ROOT),'--corpus',CORPUS,'--cases',case,'--workers','2']
    for model in ['claude-opus-5-5','gpt-6.1-sol']:
        results.append(execute(base+['--model',model,'--ai-only']))
    results.append(execute(base+['--model','claude-opus-5-5','--arms','audit']))
    pending.remove(case)
    (ROOT/'assessment-progress.json').write_text(json.dumps({'results':results,'pending':pending},indent=2)+'\n')
(ROOT/'assessment-complete.json').write_text(json.dumps({'results':results},indent=2)+'\n')
