"""Reproduce original primary14-system union from pinned saved match decisions; no models."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'runs/benchmark-validity-audit/inputs/original-benchmark-scores'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=sorted(BASE.glob('results/*/paper_*_matched.json'))
union=set();man=[];providers={}
for p in paths:
 pid=int(p.stem.split('_')[1]); data=json.loads(p.read_text())
 assert len(data)==10,(str(p),len(data))
 caught=[f'{pid:02d}-{i+1:02d}' for i,m in enumerate(data) if m.get('matched')]
 union.update(caught);providers.setdefault(p.parent.name,[]).extend(caught)
 man.append({'file':str(p.relative_to(ROOT)),'sha256':sha(p),'paper':pid,'provider':p.parent.name,'detected_ids':caught})
assert len(paths)==140 and len(providers)==14,(len(paths),len(providers))
never=sorted({f'{p:02d}-{i:02d}' for p in range(1,11) for i in range(1,11)}-union)
assert len(union)==93 and never==['02-10','04-04','05-03','05-05','05-06','07-04','10-10']
result={'benchmark_commit':'3d9188343eebd4312d3bfbde6822cfa4eaf32fb4','method':'Same matched-boolean union as pinned writeup_numbers.main_configs/detection_set; exclude _originals,_open,_run2,_run3 directories. This reproduces stored judge decisions, not their correctness.','providers':{k:len(v) for k,v in providers.items()},'n_configurations':14,'n_match_files':140,'union_count':93,'total_targets':100,'never_matched_ids':never,'matched_ids':sorted(union),'source_scripts':[{'file':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sorted(BASE.glob('*.py'))],'match_files':man}
out=ROOT/'docs/benchmark-validity-audit/original-union-reproduction.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['n_configurations','n_match_files','union_count','never_matched_ids']},indent=2))
