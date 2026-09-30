"""Normalize the three source-grounded audit batches; validate all cited quotations."""
import csv,json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/benchmark-validity-audit'; INPUT=ROOT/'runs/benchmark-validity-audit/inputs'
labels=list(csv.DictReader((INPUT/'error_insertions.csv').open()))
rows=[]
for name in ['papers-01-04.json','papers-05-08.json','papers-09-10.json']:
 batch=json.loads((OUT/name).read_text()); source_rows=batch['rows'] if isinstance(batch,dict) else batch
 for r in source_rows:
  p=int(r['paper']);i=int(r.get('ordinal',r.get('error_index',int(r['id'].split('-')[1]))))
  label=[x for x in labels if int(x['paper'])==p][i-1]
  evidence=r['evidence']+r.get('original_evidence',[])
  for e in evidence:
   lines=(ROOT/e['file']).read_text().splitlines()
   # A small number of contiguous table-cell quotations span lines.
   quote=e['quote']; line=e['line']
   assert quote in '\n'.join(lines[line-1:]),(r['id'],e)
   assert quote.startswith(lines[line-1]) or quote in lines[line-1] or '\n' in quote,(r['id'],e)
  rows.append({'id':f'{p:02d}-{i:02d}','paper':p,'ordinal':i,'annotation':label,'verdict':r['verdict'],'confidence':r['confidence'],'justified_critique':r.get('justified_critique',r.get('critique')),'annotation_alignment':r.get('annotation_alignment','See justified_critique: category denotes strongest defensible criticism, not wholesale endorsement of annotation.'),'evidence':evidence,'checks':r.get('checks',[]),'audit_batch':name})
rows.sort(key=lambda r:(r['paper'],r['ordinal']))
assert len(rows)==100 and len({r['id'] for r in rows})==100
assert all(sum(r['paper']==p for r in rows)==10 for p in range(1,11))
counts=Counter(r['verdict'] for r in rows)
never=['02-10','04-04','05-03','05-05','05-06','07-04','10-10']
result={'status':'provisional_AI_assisted_audit_not_expert_gold_standard','benchmark_commit':'3d9188343eebd4312d3bfbde6822cfa4eaf32fb4','scope':'All100 CSV targets across10 original/modified paper pairs. Stage1 reports assessed as prospective plans.','method':'Independent bounded subagent groups read modified paragraph/table/caption texts and compare originals; exact source quotation checks. Images inspected selectively, not comprehensively; see batch notes. Directed calculations where feasible. No manuscript pipeline reruns or score changes.','category_meaning':'Verdicts describe strongest defensible criticism of each edited artifact. Valid category often means internal reporting contradiction while annotation scientific consequence is unsupported. Counts are NOT counts of validated gold labels.','limitations':['AI-assisted provisional judgments, not independent human expert adjudication.','Not blinded to original/modified status or intended targets; no claim to measure blind reviewer sensitivity.','Linked supplements, cited sources, data and code not exhaustively retrieved; missing external evidence must not be equated with absence.','No new precision/recall estimates and no regrading of original model findings; benchmark judge matches not independently validated.','Text extraction retains tables/captions/notes, but graphics may carry unexamined evidence.'], 'counts':dict(counts),'per_paper':{str(p):dict(Counter(r['verdict'] for r in rows if r['paper']==p)) for p in range(1,11)},'original_14_system_union':{'detected':93,'total':100,'never_matched_ids':never,'reproduction':'Pinned benchmark/writeup_numbers.py main_configs() and detection_set(); excludes originals/open/run2/run3; no judge rerun.','never_matched_audit_counts':dict(Counter(r['verdict'] for r in rows if r['id'] in never))},'rows':rows}
(OUT/'audit-100.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
md=['# Provisional validity audit of100 planted-error targets','',result['category_meaning'],'','| ID | Audit category | Confidence | Assessment |','|---|---|---|---|']
for r in rows:md.append(f"| {r['id']} | {r['verdict']} | {r['confidence']} | {r['justified_critique'].replace('|','/')} |")
md += ['','Exact quotations, paths and line references: [audit-100.json](audit-100.json). Fuller batch reports: [papers1–4](papers-01-04.md), [papers5–8](papers-05-08.md), [papers9–10](papers-09-10.md).']
(OUT/'audit-100.md').write_text('\n'.join(md)+'\n')
print(json.dumps({'rows':len(rows),'counts':counts,'never_matched':result['original_14_system_union']['never_matched_audit_counts']},indent=2))
