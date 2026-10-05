"""Run the separate frozen repaired assessment; never replace v1/v3 artifacts."""
import concurrent.futures, json, os, subprocess, threading, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LAUNCH=json.loads((ROOT/'launch.json').read_text())
METHOD=json.loads((ROOT/'assessment-method-v2.json').read_text())
CODE=Path(METHOD['code'])
PYTHON='/home/lukas/Documents/Coding/coarse-socpsy/.venv/bin/python'
CORPUS='/home/lukas/Documents/Coding/coarse-socpsy/eval/corpus/cache/open-review-curation-20261002'
ENV={k:v for k,v in os.environ.items() if k not in {'ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','OPENAI_API_KEY'}}
ENV['PYTHONPATH']=str(CODE/'src')
LOCK=threading.Lock();RESULTS=[]

def save(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)

def execute(case,step,command):
 with (ROOT/f'assessment-v2-{case}.log').open('a') as log:
  log.write(json.dumps({'at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'step':step,'command':command})+'\n');log.flush()
  result=subprocess.run(command,cwd=CODE,env=ENV,stdout=log,stderr=subprocess.STDOUT)
 row={'case':case,'step':step,'command':command,'returncode':result.returncode}
 with LOCK:
  RESULTS.append(row);save(ROOT/'assessment-v2-progress.json',{'method':METHOD,'results':RESULTS})
 print(json.dumps(row),flush=True)
 return row

def assess(case):
 command=[PYTHON,str(CODE/'eval/assess_criticisms.py'),'--root',str(ROOT),'--cases',case]
 first=execute(case,'unique-criticisms',command)
 if first['returncode']:
  execute(case,'unique-criticisms-retry',command)
 # The packet independently gates each arm and records every exclusion.
 provenance=json.loads((ROOT/'criticism-packets-v2'/f'{case}.origins.json').read_text())
 arms=[a for a in ['plain','holistic','audit'] if a in provenance['source_hashes']]
 base=[PYTHON,str(CODE/'eval/compare_development_reviews.py'),'--root',str(ROOT),'--corpus',CORPUS,'--cases',case,'--workers','2','--arms',*arms]
 if len(arms)>=2:
  for model in ['claude-opus-5-5','gpt-6.1-sol']:
   execute(case,'whole-report-v4-'+model,base+['--model',model,'--ai-only'])
 if 'audit' in arms:
  execute(case,'human-comparators-v4',base[:base.index('--arms')]+['--arms','audit','--model','claude-opus-5-5'])
 return {'case':case,'included_arms':arms,'excluded':provenance['excluded']}

pending=[x['case'] for x in LAUNCH['inputs']];submitted=set();futures={};outcomes=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 while pending or futures:
  for case in list(pending):
   if all((ROOT/'generation'/f'{mode}-{case}.json').exists() for mode in ['plain','pipeline']):
    futures[pool.submit(assess,case)]=case;pending.remove(case);submitted.add(case)
  finished=[f for f in futures if f.done()]
  for f in finished:
   case=futures.pop(f)
   try:outcomes.append(f.result())
   except Exception as exc:outcomes.append({'case':case,'error':str(exc)})
  if pending and (ROOT/'generation-complete.json').exists():
   outcomes.extend({'case':case,'error':'generation completion lacks case markers'} for case in pending);pending=[]
  if pending or futures:time.sleep(10)
errors=[r for r in RESULTS if r['returncode']]
case_errors=[r for r in outcomes if r.get('error')]
exclusions=[r for r in outcomes if r.get('excluded')]
save(ROOT/'assessment-v2-complete.json',{'method':METHOD,'status':'completed_with_errors' if errors or case_errors else 'completed_with_exclusions' if exclusions else 'completed','results':RESULTS,'cases':outcomes,'errors':errors,'case_errors':case_errors,'exclusions':exclusions})
