"""Rewrap all completed judgments offline; preserve raw calls and original conditions."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
METHOD=json.loads((ROOT/'assessment-method-v2.json').read_text());CODE=Path(METHOD['offline_rewrap']['code'])
if not (ROOT/'assessment-v2-complete.json').exists():raise SystemExit('Wait for native v2 assessment completion before rewrapping')
if not (ROOT/'assessment-complete.json').exists():raise SystemExit('Wait for original assessment completion before rederiving historical quotes')
for driver in ROOT.glob('recover_*_assessment.py'):
 case=driver.stem.removeprefix('recover_').removesuffix('_assessment')
 marker=ROOT/('assessment-v2-'+case+'-additional-recovery.json')
 if not marker.exists():raise SystemExit('Wait for active additional recovery: '+case)
 if json.loads(marker.read_text())['returncode'] and case!='niemeyer':raise SystemExit('Additional recovery failed: '+case)
 if case=='niemeyer' and json.loads(marker.read_text())['returncode'] and not (ROOT/'partial-criticism-assessments-v2/gpt-6.1-sol/niemeyer.json').exists():raise SystemExit('Explicit partial diagnostic required for failed Niemeyer primary output')
ENV={k:v for k,v in os.environ.items() if k not in {'ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','OPENAI_API_KEY','LC_ALL'}}
ENV['PYTHONPATH']=str(CODE/'src');ENV['PATH']='/home/lukas/.local/bin:/usr/local/bin:/usr/bin:/bin'
PYTHON='/home/lukas/Documents/Coding/coarse-socpsy/.venv/bin/python'
def hashes():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'criticism-judge-raw-v2').glob('*/*/*.json')}
for case in ['bonetto','satrevik','ziano','heyman','mackinnon']:
 for model in ['claude-opus-5-5','gpt-6.1-sol']:
  d=json.loads((ROOT/'criticism-assessments-v2'/model/(case+'.json')).read_text())
  if not Path(d['matcher_module']).is_relative_to(CODE):raise SystemExit('First-five offline rewrap still pending')
before=hashes();results=[]
script_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['provenance_audit.py','offline_finalize.py','summarize.py']}
commands=[
 [PYTHON,str(ROOT/'rewrap_niemeyer_opus.py')],
 [PYTHON,str(ROOT/'provenance_audit.py')]]
with (ROOT/'offline-finalize.log').open('a') as log:
 for cmd in commands:
  log.write(json.dumps({'at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'command':cmd})+'\n');log.flush()
  p=subprocess.run(cmd,cwd=CODE,env=ENV,stdout=log,stderr=subprocess.STDOUT)
  results.append({'command':cmd,'returncode':p.returncode})
  if p.returncode:break
unchanged=hashes()==before
record={'reused_prior_offline_work':'First-five --offline rewrap, completed-corpus v1 rederivation and candidate-only impact scan already done; final provenance audit rechecks 11 valid native outputs, the explicitly excluded partial, and 12 historical records rather than repeating calculations.','reporting_script_sha256':script_hashes,'method':METHOD['offline_rewrap'],'results':results,'raw_call_artifacts_unchanged':unchanged,'raw_artifact_count':len(before),'no_model_calls':True,'status':'complete' if unchanged and len(results)==len(commands) and all(r['returncode']==0 for r in results) else 'failed'}
(ROOT/'offline-finalize.json').write_text(json.dumps(record,indent=2)+'\n')
if record['status']=='complete':
 with (ROOT/'offline-finalize.log').open('a') as log:
  command=[PYTHON,str(ROOT/'summarize.py')];p=subprocess.run(command,cwd=CODE,env=ENV,stdout=log,stderr=subprocess.STDOUT)
  record['render_returncode']=p.returncode
  if p.returncode:record['status']='failed'
 (ROOT/'offline-finalize.json').write_text(json.dumps(record,indent=2)+'\n')
print(record['status'],record['raw_artifact_count'],'unchanged raw judge artifacts')
raise SystemExit(0 if record['status']=='complete' else 2)
