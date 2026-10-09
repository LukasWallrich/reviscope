"""Final-render guard regressions using in-memory mutations only."""
import hashlib,json,runpy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
if not json.loads((ROOT/'assessment-summary.json').read_text())['final_ready']:raise SystemExit('Run after verified offline finalization')
real_bytes=Path.read_bytes;real_text=Path.read_text
results=[]
for kind,expected in [('comparison_bytes','Comparison changed since final provenance audit'),('native_raw_digest','Native assessment changed since final provenance audit')]:
 def bytes_(p):
  data=real_bytes(p)
  return data+b'changed-in-memory' if kind=='comparison_bytes' and 'comparisons-v4' in p.parts and p.name=='audit-vs-holistic.json' else data
 def text_(p,*a,**kw):
  data=real_text(p,*a,**kw)
  if kind=='native_raw_digest' and 'criticism-assessments-v2' in p.parts and p.name=='bonetto.json':
   d=json.loads(data);d['raw_judge_sha256']='changed-in-memory';return json.dumps(d)
  return data
 with patch.object(Path,'read_bytes',bytes_),patch.object(Path,'read_text',text_):
  try:runpy.run_path(str(ROOT/'summarize.py'));raise AssertionError('Stale artifact was accepted')
  except ValueError as e:
   if expected not in str(e):raise
   results.append({'in_memory_change':kind,'rejected':True,'expected_guard':expected})
record={'checks':results,'no_model_calls':True,'existing_campaign_artifacts_unchanged':True,'render_script_sha256':hashlib.sha256((ROOT/'summarize.py').read_bytes()).hexdigest(),'test_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':'Engineering provenance guards only; not evidence of scientific quality.'}
(ROOT/'preflight/render-provenance-negative-check.json').write_text(json.dumps(record,indent=2)+'\n')
print(len(results),'negative final-render checks passed')
