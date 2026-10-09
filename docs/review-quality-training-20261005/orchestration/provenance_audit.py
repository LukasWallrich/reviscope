"""Read-only final assessment provenance audit. Never invoke a model backend."""
import hashlib, importlib.util, json, os, runpy, sys
# Match the original systemd launch environment policy; values never enter artifacts.
for key in ["ANTHROPIC_API_KEY","ANTHROPIC_AUTH_TOKEN","ANTHROPIC_BASE_URL","OPENAI_API_KEY","LC_ALL"]:os.environ.pop(key,None)
from pathlib import Path
ROOT=Path(__file__).resolve().parent
METHOD=json.loads((ROOT/'assessment-method-v2.json').read_text())
CODE=Path(METHOD['offline_rewrap']['code'])
sys.path[:0]=[str(CODE/'src'),str(CODE/'eval')]
from reviscope.evaluation import build_pairwise_cases, comparison_parts
from reviscope.backend import ClaudeBackend, CodexBackend
import assess_criticisms as ac
import compare_development_reviews as comp

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(d):return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
def backend(model):return ClaudeBackend(model,effort='high',tools=False) if model=='claude-opus-5-5' else CodexBackend(model,effort='high',tools=False)
def check(ok,msg):
 if not ok:raise ValueError(msg)

launch=read(ROOT/'launch.json');checks=[];missing=[];partials=[]
script_hashes={name:sha(ROOT/name) for name in ['provenance_audit.py','offline_finalize.py','summarize.py']}
for label,record in [('generation',launch),('native_judge_calls',METHOD),('offline_rewrap',METHOD['offline_rewrap'])]:
 code=Path(record['code']);frozen=runpy.run_path(str(code/'eval/run_known_errors.py'))
 check(frozen['code_digest'](code)==record['code_sha256'],f'Changed {label} snapshot')
 checks.append({'condition':label,'code':str(code),'code_sha256':record['code_sha256']})
# The actual-call method and final bookkeeping share the same literal judge instruction.
spec=importlib.util.spec_from_file_location('original_assessor',Path(METHOD['code'])/'eval/assess_criticisms.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
check(ac.INSTRUCTION==original.INSTRUCTION,'Native judge instruction changed during rewrap')
spec=importlib.util.spec_from_file_location('original_evaluation',Path(METHOD['code'])/'src/reviscope/evaluation.py')
original_eval=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original_eval;spec.loader.exec_module(original_eval)
rows=[]
for entry in launch['inputs']:
 case=entry['case']
 for model in ['claude-opus-5-5','gpt-6.1-sol']:
  path=ROOT/'criticism-assessments-v2'/model/f'{case}.json'
  if not path.exists():
   missing.append(str(path));partial=ROOT/'partial-criticism-assessments-v2'/model/f'{case}.json'
   if partial.exists():
    q=read(partial);raw=read(Path(q['raw_response_artifact']));packet=read(Path(q['packet_snapshot']))
    check(case=='niemeyer' and model=='gpt-6.1-sol','Unexpected partial stratum')
    check(sha(Path(q['raw_response_artifact']))==q['raw_response_sha256'] and sha(Path(q['packet_snapshot']))==q['packet_sha256'],'Changed partial raw/packet')
    check(sha(Path(q['call_log']))==q['call_log_sha256'],'Partial call log changed')
    ids=[x['item_id'] for x in raw['assessments']];members=[i for g in raw['groups'] for i in g['member_ids']];expected=set(q['origins'])
    check(set(ids)==expected and len(ids)==len(expected),'Incomplete partial item inventory')
    check(set(members)<=expected and len(members)==len(set(members)) and sorted(expected-set(members))==q['ungrouped_ids'],'Invalid partial groups')
    check(q['assessments']==[ac.checked_labels(x,packet['manuscript']) for x in raw['assessments']] and q['groups']==raw['groups'],'Changed partial model fields')
    for arm,digest_ in q['source_hashes'].items():check(sha(ROOT/'reviews'/arm/case/'review.json')==digest_,'Partial archived review changed')
    partials.append({'case':case,'model':model,'artifact':str(partial),'artifact_sha256':sha(partial),'ungrouped_ids':q['ungrouped_ids'],'assessments':len(ids),'input_association':q['input_association'],'excluded_from_primary_protocol':True})
   continue
  d=read(path);packet=read(Path(d['packet_snapshot']));raw=read(Path(d['raw_judge_artifact']))
  check(sha(Path(d['packet_snapshot']))==d['packet_sha256'],'Packet changed')
  check(sha(Path(d['raw_judge_artifact']))==d['raw_judge_sha256'],'Raw response changed')
  check(d['origins']==d['packet_provenance']['origins'],'Different origin map')
  expected=digest({'instruction':ac.INSTRUCTION,'packet':packet,'backend':backend(model).identity,'schema':ac.QualityAssessment.model_json_schema(),'protocol':'unique-criticism-v2'})
  check(d['cache_key']==raw['cache_key']==expected,f'Different raw model-call identity {case}/{model}: stored {d["cache_key"]}, reconstructed {expected}, stored backend {d["backend_identity"]}, current {backend(model).identity}')
  if 'packet_sha256' in raw:check(raw['packet_sha256']==d['packet_sha256'],'Raw packet identity differs')
  matcher=Path(d['matcher_module']);method=CODE/'eval/assess_criticisms.py' if matcher.is_relative_to(CODE) else Path(METHOD['code'])/'eval/assess_criticisms.py'
  check(d['method_sha256']==hashlib.sha256((sha(method)+sha(matcher)).encode()).hexdigest(),'Incorrect derivation method hash')
  for arm,s in d['source_hashes'].items():check(sha(ROOT/'reviews'/arm/case/'review.json')==s,'Review changed')
  check({r['item_id'] for r in raw['result']['assessments']}==set(d['origins']),'Raw ID inventory differs')
  if matcher.is_relative_to(CODE):
   check(d['assessments']==[ac.checked_labels(x,packet['manuscript']) for x in raw['result']['assessments']],'Derived fields differ from raw rewrap')
   check(all('quote_check_passed' in x for x in d['assessments']),'Missing final quote flags')
   check(all('present_in_audit' in x for x in d['packet_provenance']['holistic_not_published_in_audit']),'Missing final nested provenance')
  else:
   for r,old in zip(d['assessments'],raw['result']['assessments']):check(r['item_id']==old['item_id'] and r['raw_claim_status']==old['claim_status'],'Raw label altered')
  rows.append({'case':case,'model':model,'packet_sha256':d['packet_sha256'],'raw_judge_sha256':d['raw_judge_sha256'],'method_sha256':d['method_sha256'],'matcher_module':str(matcher),'rewrapped_offline':matcher.is_relative_to(CODE),'items':len(d['assessments']),'artifact_sha256':sha(path)})
comparisons=[]
corpus=Path('/home/lukas/Documents/Coding/coarse-socpsy/eval/corpus/cache/open-review-curation-20261002')
for p in sorted((ROOT/'comparisons-v4').glob('*/*/*.json')):
 d=read(p);case=d['case'];prepared=read(corpus/case/'prepared.json');manuscript=Path(prepared['manuscript_text'])
 texts={};hashes={'manuscript':sha(manuscript)}
 for arm in [d['left'],d['right']]:
  if arm.startswith('human-'):
   ref=next(x for x in prepared['human_reviews'] if 'human-'+x['id']==arm);q=Path(ref['path']);check(sha(q)==ref['text_sha256'],'Human input changed');texts[arm]=q.read_text()
  else:
   q=ROOT/'reviews'/arm/case/'review.json';texts[arm]=comp.review_text(read(q));comp.checked_audit(q,prepared['paper_id'],prepared['manuscript_text_sha256'],prepared['profile'])
  hashes[arm]=sha(q)
 check(hashes==d['source_hashes'],'Comparison input hashes changed')
 paper={'paper_id':prepared['paper_id'],'manuscript':manuscript.read_text(),'candidate_review':texts[d['left']],'reference_review':texts[d['right']]}
 pairs=build_pairwise_cases([paper],seed=42,order_swap=True);parts=[comparison_parts(c) for c in pairs]
 check(parts==[original_eval.comparison_parts(c) for c in pairs],'Actual and rewrap whole-report prompt differ')
 expected=digest({'input':parts,'backend':backend(d['model']).identity,'protocol':'development-criticism-comparison-v4'})
 check(expected==d['cache_key'],'Whole-report call key differs')
 check(not d['invalid'] and len(d['judgments'])==2,'Incomplete comparison')
 comparisons.append({'case':case,'model':d['model'],'left':d['left'],'right':d['right'],'artifact_sha256':sha(p),'instruction_sha256':hashlib.sha256(parts[0][0].encode()).hexdigest(),'actual_prompt_policy_sha256':sha(Path(METHOD['code'])/'src/reviscope/evaluation.py'),'literal_prompt_equal_to_final_wrapper':True,'original_prompt_provenance_missing':'prompt_policy_module' not in d})
controls=[]
for name in ['assessor-control-results.json','assessor-control-results-extended.json','assessor-control-results-followup.json','assessor-source-only-results.json']:
 p=ROOT/name
 if p.exists():controls.append({'artifact':str(p),'artifact_sha256':sha(p),'scope':'Separate post-hoc protocol probes, never native case counts','recorded_method_sha256':read(p).get('method_sha256')})
source_control=[]
for model in ['claude-opus-5-5','gpt-6.1-sol']:
 p=ROOT/'criticism-assessments-v2'/model/'heyman-source-only-control.json'
 if not p.exists():continue
 d=read(p);packet=read(Path(d['packet_snapshot']));raw=read(Path(d['raw_judge_artifact']))
 check(sha(Path(d['packet_snapshot']))==d['packet_sha256'] and sha(Path(d['raw_judge_artifact']))==d['raw_judge_sha256'],'Changed source-only control artifacts')
 check(d['cache_key']==digest({'instruction':ac.INSTRUCTION,'packet':packet,'backend':d['backend_identity'],'schema':ac.QualityAssessment.model_json_schema(),'protocol':'unique-criticism-v2'}),'Changed source-only raw call inputs')
 code09=Path(METHOD['code']);old_hash=hashlib.sha256((sha(code09/'eval/assess_criticisms.py')+sha(code09/'src/reviscope/verification.py')).encode()).hexdigest()
 check(d['method_sha256']==old_hash,'Source-only live derivation does not match archived 09 code')
 source_control.append({'model':model,'executed_from_live_module':d['matcher_module'],'recorded_method_sha256':d['method_sha256'],'matches_archived09_derivation_content':True,'raw_judge_sha256':d['raw_judge_sha256'],'raw_claim_status':raw['result']['assessments'][0]['claim_status'],'limits':'Executed from live eval folder, not the frozen native trial; post-hoc control only. Raw labels do not depend on quotation matching.'})
expected_set=set()
for entry in launch['inputs']:
 prepared=read(corpus/entry['case']/'prepared.json')
 for model in ['claude-opus-5-5','gpt-6.1-sol']:
  for left,right in [('holistic','plain'),('audit','holistic'),('audit','plain')]:expected_set.add((entry['case'],model,left,right))
 for human in prepared['human_reviews']:expected_set.add((entry['case'],'claude-opus-5-5','audit','human-'+human['id']))
actual_set={(d['case'],d['model'],d['left'],d['right']) for d in comparisons}
check(actual_set<=expected_set,'Unexpected comparison jobs')
expected_comparisons=len(expected_set)
historical=[]
for entry in launch['inputs']:
 for model in ['claude-opus-5-5','gpt-6.1-sol']:
  p=ROOT/'criticism-assessments-rederived'/model/(entry['case']+'.json')
  if not p.exists():missing.append(str(p));continue
  d=read(p);meta=d['rederivation'];original_path=Path(meta['original_artifact']);original_path=original_path if original_path.is_absolute() else ROOT.parents[1]/original_path
  check(original_path.resolve()==(ROOT/'criticism-assessments'/model/(entry['case']+'.json')).resolve(),'Historical original path is not canonical')
  old=read(original_path)
  check(sha(original_path)==meta['original_sha256'],'Changed original v1 judgment')
  check(Path(meta['matcher_module']).is_relative_to(CODE) and meta['method_sha256']==ac.method_hash(),'Wrong v1 rederivation method')
  check(all(d[k]==v for k,v in old.items() if k!='assessments'),'Changed v1 model metadata/groups')
  text=Path(entry['input']).read_text();expected_rows=[]
  for x in old['assessments']:
   q=ac.checked_labels(x,text);q['original_derived_claim_status']=x['claim_status'];q['original_limits']=x['limits']
   if q['quote_check_passed']:q['limits']=x['limits'].replace(' Deterministic check: missing relevant exact manuscript evidence.','')
   expected_rows.append(q)
  check(d['assessments']==expected_rows,'Changed v1 raw/derived fields')
  historical.append({'case':entry['case'],'model':model,'original_sha256':meta['original_sha256'],'rederived_sha256':sha(p),'changed_labels':meta['changed_labels']})
report_identities=[]
for entry in launch['inputs']:
 for arm in ['plain','holistic','audit']:
  p=ROOT/'reviews'/arm/entry['case']/'review.json'
  row=comp.checked_audit(p,entry['paper_id'],entry['manuscript_sha256'],entry['profile'])
  report_identities.append({'case':entry['case'],'arm':arm,'review_sha256':sha(p),'audit_rules_sha256':row['audit_rules_sha256'],'audit_artifact_sha256':sha(p.parent/'tool-audit.json'),'verdict':row['verdict']})
complete=(ROOT/'assessment-v2-complete.json').exists() and not missing and len(rows)==2*len(launch['inputs']) and all(x['rewrapped_offline'] for x in rows) and actual_set==expected_set
auxiliary=set(ROOT.glob('*status-*.json')) | set(ROOT.glob('*control*results*.json')) | set((ROOT/'preflight').glob('*.json')) | set((ROOT/'generation').glob('*.json')) | set(ROOT.glob('assessment-v2-*-additional-recovery.json'))
auxiliary.update(ROOT.glob('assessment-v2-*-recovery-association.json'));auxiliary.update((ROOT/'recovery-history').glob('*.json'))
for dirname in ['criticism-assessments','criticism-assessments-v2']:
 auxiliary.update((ROOT/dirname).glob('*/*.invalid.json'));auxiliary.update((ROOT/dirname).glob('*/history/*.invalid-*.json'))
for dirname in ['comparisons','comparisons-v4']:auxiliary.update((ROOT/dirname).glob('*/*/history/*.json'))
aux_hashes={str(p):sha(p) for p in sorted(auxiliary)}
diagnostic_complete=not complete and len(rows)==2*len(launch['inputs'])-1 and len(missing)==len(partials)==1 and all(x['rewrapped_offline'] for x in rows) and actual_set==expected_set and len(historical)==2*len(launch['inputs'])
result={'status':'complete_verified' if complete else 'diagnostic_complete_with_primary_format_failure' if diagnostic_complete else 'interim_verified_available','partial_diagnostics':partials,'no_model_calls':True,'reporting_script_sha256':script_hashes,'auxiliary_artifact_sha256':aux_hashes,'historical_comparison_artifacts':[{"artifact":str(p),"artifact_sha256":sha(p)} for p in sorted((ROOT/'comparisons').glob('*/*/*.json'))],'controls':controls,'source_only_controls':source_control,'historical_v1_rederivation':historical,'report_identities':report_identities,'snapshot_checks':checks,'native_assessments':rows,'whole_report_comparisons':comparisons,'missing':missing,'expected_comparisons':expected_comparisons,'limits':'Identity checks, not scientific correctness. Initial v4 output lacks prompt provenance fields; actual launch logs bind calls to the verified 09dd60b0 snapshot, and full reconstructed literal input/cache keys match. Final metadata does not imply a new model call.'}
check(script_hashes=={name:sha(ROOT/name) for name in script_hashes},'Reporting scripts changed during provenance audit')
(ROOT/'assessment-provenance-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],len(rows),'native assessments;',len(comparisons),'whole-report comparisons')
