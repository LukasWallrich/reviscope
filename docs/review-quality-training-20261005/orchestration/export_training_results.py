"""Archive bounded diagnostics and orchestration; never copy manuscript/PDF/human text."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
OUT=REPO/'docs/review-quality-training-20261005';OUT.mkdir(exist_ok=True)
d=json.loads((ROOT/'assessment-summary.json').read_text())
if not d['final_ready']:raise SystemExit('Export only the verified final condition')
keys=['generation_condition','repaired_assessment_method','method','reports','criticism_counts','native_strata','native_judge_attempts','resource_diagnostics','generation_wall_diagnostics','errors','completion','additional_recoveries','offline_finalize','reporting_script_sha256','final_ready','partial_diagnostics','comparison_history','provenance_audit']
safe={k:d.get(k) for k in keys}
safe['comparisons']=[{k:v for k,v in x.items() if k!='order_rationales'} for x in d['comparisons']]
safe['controls']=[{'condition':x['condition'],'artifact_sha256':x['artifact_sha256'],'results':[{k:v for k,v in row.items() if k not in {'reasoning','limits'}} for row in x['results']],'source_hashes':x.get('source_hashes'),'method_sha256':x.get('method_sha256')} for x in d['controls']]
safe['targeted_checks']=[{'artifact':x['artifact'],'sha256':x['sha256'],'selection':x['record'].get('selection'),'bounded_conclusion':x['record'].get('bounded_assessment') or x['record'].get('bounded_conclusion') or x['record'].get('qualification') or x['record'].get('limits')} for x in d['targeted_checks']]
safe['limits']='Training diagnostic; native bundled model opinions and repeat labels, not precision, recall, independent validation or causal improvement. Full source texts and judge rationales remain local; figures requiring pixels remain unassessed.'
(OUT/'summary.json').write_text(json.dumps(safe,indent=2,ensure_ascii=False)+'\n')
for name in ['assessment-provenance-audit.json','offline-finalize.json','quote-label-rederivation.json']:(OUT/name).write_bytes((ROOT/name).read_bytes())
for name in ['reasoning-ledger-uptake-check.json','reporting-provenance-negative-check.json','render-provenance-negative-check.json']:
 p=ROOT/'preflight'/name
 if p.exists():(OUT/name).write_bytes(p.read_bytes())
scripts=OUT/'orchestration';scripts.mkdir(exist_ok=True)
for name in ['campaign.py','assess_campaign.py','assess_campaign_v2.py','criticism_audit.py','provenance_audit.py','provenance_negative_checks.py','render_provenance_negative_checks.py','offline_finalize.py','summarize.py','recover_mackinnon_assessment.py','recover_niemeyer_assessment.py','retain_partial_niemeyer.py','rewrap_niemeyer_opus.py','export_training_results.py']:
 p=ROOT/name
 if p.exists():(scripts/name).write_bytes(p.read_bytes())
(OUT/'orchestration-sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts.glob('*.py')},indent=2)+'\n')
(OUT/'implementation-files.txt').write_text(subprocess.check_output(['git','diff','--name-only','a977767..48edf35'],cwd=REPO,text=True))
(OUT/'all-integrated-pipeline-files.txt').write_text(subprocess.check_output(['git','diff','--name-only','c98e67b..48edf35'],cwd=REPO,text=True))
(OUT/'README.md').write_text('''# Training diagnostic records

See [the results](../REVIEW_QUALITY_TRAINING_RESULTS.md). These artifacts contain
bounded diagnostics and content hashes, not manuscript, PDF or human-review copies.
Model labels and native item counts are not scientific correctness estimates.

Canonical local artifacts are in
`/home/lukas/Documents/Coding/reviscope-reasoning-assessment/runs/reasoning-quality-20261005`.
The orchestration copies are inspectable records of the executed scripts. They derive
ROOT from their own location; restore them to the canonical run root with retained data
before executing, rather than running these archive copies in place. Generation and
assessment modules are separately frozen at the paths and hashes in the provenance audit.
`offline_finalize.py` uses retained raw calls and refuses model calls. Four negative
provenance checks and two final-render checks test engineering guards only.

All Meta-Psychology data are training/development; an independent corpus and qualified
expert assessment remain to be chosen. Main is checked out separately in
`/home/lukas/Documents/Coding/reviscope-main`; implementation branch/worktree is
`reasoning-assessment` in `/home/lukas/Documents/Coding/reviscope-reasoning-assessment`.
The shared `coarse-socpsy` checkout remains `known-error-benchmark` at `a977767`.
Use explicit PYTHONPATH for isolated code; the shared editable virtual environment
continues to point at the original checkout. Nothing was pushed or publicly published.
''')
print('Archived verified bounded diagnostics and orchestration:',OUT)
