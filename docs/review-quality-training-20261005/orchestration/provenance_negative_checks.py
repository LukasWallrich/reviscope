"""Inject changed inputs in memory; never modify artifacts or call a model."""
import hashlib,json,os,runpy,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
CODE=Path(json.loads((ROOT/'assessment-method-v2.json').read_text())['offline_rewrap']['code'])
sys.path[:0]=[str(CODE/'src'),str(CODE/'eval')]
from reviscope.backend import ClaudeBackend,CodexBackend
real_bytes=Path.read_bytes;real_text=Path.read_text
results=[]
def no_model(*args,**kwargs):raise AssertionError('Unexpected model call in provenance audit')
for kind,expected in [('raw_bytes','Raw response changed'),('cache_key','Different raw model-call identity'),('origin_map','Different origin map'),('method_hash','Incorrect derivation method hash')]:
 def bytes_(p):
  data=real_bytes(p)
  return data+b'\n' if kind=='raw_bytes' and 'criticism-judge-raw-v2' in p.parts and 'bonetto' in p.parts else data
 def text_(p,*a,**kw):
  data=real_text(p,*a,**kw)
  if kind!='raw_bytes' and 'criticism-assessments-v2' in p.parts and p.name=='bonetto.json':
   d=json.loads(data)
   if kind=='cache_key':d['cache_key']='changed-in-memory'
   elif kind=='origin_map':d['origins']={}
   elif kind=='method_hash':d['method_sha256']='changed-in-memory'
   return json.dumps(d)
  return data
 with patch.object(Path,'read_bytes',bytes_),patch.object(Path,'read_text',text_),patch.object(ClaudeBackend,'generate',no_model),patch.object(CodexBackend,'generate',no_model):
  try:runpy.run_path(str(ROOT/'provenance_audit.py'));raise AssertionError('Changed provenance was accepted')
  except ValueError as e:
   if expected not in str(e):raise
   results.append({'in_memory_change':kind,'rejected':True,'expected_guard':expected})
record={'checks':results,'no_model_calls':True,'no_artifact_mutations':True,'audit_script_sha256':hashlib.sha256((ROOT/'provenance_audit.py').read_bytes()).hexdigest(),'test_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':'Engineering guard checks; not evidence of scientific review quality.'}
(ROOT/'preflight/reporting-provenance-negative-check.json').write_text(json.dumps(record,indent=2)+'\n')
print(len(results),'negative provenance checks passed; no model calls or artifact mutations')
