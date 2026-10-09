"""Descriptive training diagnostics; keep original and repaired judge conditions separate."""
from collections import Counter
import hashlib, html, json, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LAUNCH=json.loads((ROOT/'launch.json').read_text())
METHOD=json.loads((ROOT/'assessment-method-v2.json').read_text()) if (ROOT/'assessment-method-v2.json').exists() else None
OUT=ROOT/'tailnet-preview';E=html.escape
STYLE='<style>body{font:16px/1.55 system-ui,sans-serif;max-width:1150px;margin:3rem auto;padding:0 1.5rem;color:#16202b;background:#fafbf9}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #cdd5d3;padding:.65rem;vertical-align:top}a{color:#075b75}.note{background:#e7eeeb;padding:1rem}small{color:#52615e}details{border-bottom:1px solid #cdd5d3;padding:.8rem 0}summary{cursor:pointer}</style>'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def visible_unconfirmed(d):
 manuscripts={x['id'] for x in d.get('sources',[]) if x.get('kind')=='manuscript'}
 return [f['id'] for f in d.get('findings',[]) if f['status']=='unresolved' and f.get('verifier_status')=='unresolved' and any(e['source_id'] in manuscripts and e.get('location') for e in f['evidence'])]
def published(d):return d.get('issues',[]) if 'issues' in d else [f for f in d['findings'] if f['editorial_disposition']=='publish' and f['status'] not in {'candidate','unverified','unresolved','contradicted'}]
summary={'generation_condition':LAUNCH,'repaired_assessment_method':METHOD,'method':'Training diagnostic; native bundled items, model opinions, not expert precision or independent validation','reports':[],'comparisons':[],'criticism_counts':[],'disagreements':[],'packet_provenance':{},'errors':[],'resource_diagnostics':[],'generation_wall_diagnostics':[],'controls':[]}
completion=read(ROOT/'assessment-v2-complete.json') if (ROOT/'assessment-v2-complete.json').exists() else None
offline=read(ROOT/'offline-finalize.json') if (ROOT/'offline-finalize.json').exists() else None
prov=read(ROOT/'assessment-provenance-audit.json') if (ROOT/'assessment-provenance-audit.json').exists() else None
script_hashes={name:sha(ROOT/name) for name in ['provenance_audit.py','offline_finalize.py','summarize.py']}
final_ready=bool(completion and offline and offline['status']=='complete' and prov and prov['status'] in {'complete_verified','diagnostic_complete_with_primary_format_failure'} and prov['reporting_script_sha256']==script_hashes and offline['reporting_script_sha256']==script_hashes)
if final_ready:
 for path,digest in prov['auxiliary_artifact_sha256'].items():
  if sha(Path(path))!=digest:raise ValueError('Auxiliary assessment artifact changed since final audit')
state=('Finished diagnostic: 11/12 primary item-judge outputs; explicit grouping failure retained' if prov and prov['status']=='diagnostic_complete_with_primary_format_failure' else 'Finished: verified offline rewrap; retained recovered errors below') if final_ready else 'Interim: assessment or offline provenance verification incomplete'
summary.update(reporting_script_sha256=script_hashes,final_ready=final_ready,offline_finalize=offline)
native_audit={(x['case'],x['model']):x for x in prov.get('native_assessments',[])} if prov else {}
comparison_audit={(x['case'],x['model'],x['left'],x['right']):x for x in prov.get('whole_report_comparisons',[])} if prov else {}
legacy_audit={x['artifact']:x['artifact_sha256'] for x in prov.get('historical_comparison_artifacts',[])} if prov else {}
if completion:summary['completion']=completion
summary['additional_recoveries']=[{**read(p),'record_artifact':str(p),'record_sha256':sha(p)} for p in [*ROOT.glob('assessment-v2-*-additional-recovery.json'),*(ROOT/'recovery-history').glob('*.json')]]
parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ReviScope review-quality assessment</title>'+STYLE,'<h1>ReviScope review-quality assessment</h1>',f'<p>{E(state)} · updated {E(time.strftime("%Y-%m-%d %H:%M:%S %Z"))}</p>','<p><a href="/">Live report dashboard</a></p>','<p class="note"><strong>Training/development evidence.</strong> All six Meta-Psychology cases are training data. One fresh generation replicate, frozen code and pinned submitted text. Model preferences and criticism labels are diagnostic opinions, not expert correctness or generalization. The default specialist strategy is not tested here. Independent validation remains to be selected.</p>','<p>Generation remains frozen at f7aab38. Post-freeze numeric quote matching and metacheck failure-reporting repairs are separate engineering changes. The repaired criticism condition (v2) and whole-report prompt (v4) are separate from original v1/v3 judgments; differences mix protocol changes and model sampling, not a causal repair effect.</p>','<h2>Report completion and excluded author-visible concerns</h2><table><tr><th>Case / arm</th><th>Completion / source audit</th><th>Issued native items</th><th>Author-visible unresolved concerns excluded</th><th>Verifier/status-supported but not published</th></tr>']
for entry in LAUNCH['inputs']:
 case=entry['case']
 for arm in ['plain','holistic','audit']:
  p=ROOT/'reviews'/arm/case/'review.json'
  if not p.exists():continue
  d=read(p);audit=p.parent/'tool-audit.json';verdict=read(audit)[0]['verdict'] if audit.exists() else 'pending'
  count=len(published(d));uncertain=visible_unconfirmed(d)
  row={'case':case,'arm':arm,'partial':d.get('partial',False),'audit':verdict,'issued':count,'unconfirmed_author_visible_excluded':uncertain,'candidate_count':len(d.get('candidates',[])),'supported_not_published':[f['id'] for f in d.get('findings',[]) if (f.get('verifier_status')=='supported' or f['status'] in {'verified_deterministic','recomputed','llm_supported','supported'}) and f['editorial_disposition']!='publish'],'finding_status_dispositions':dict(Counter(f['status']+'/'+f['editorial_disposition'] for f in d.get('findings',[])))}
  held_ids=set(row['supported_not_published']);row['supported_not_published_dispositions']=dict(Counter(f['editorial_disposition'] for f in d.get('findings',[]) if f['id'] in held_ids))
  summary['reports'].append(row)
  parts.append(f'<tr><td><a href="{arm}-{case}.html">{E(case)} / {E(arm)}</a></td><td>{"partial" if row["partial"] else "complete"} / {E(verdict)}</td><td>{count}</td><td>{len(uncertain)}{": "+E(", ".join(uncertain)) if uncertain else ""}</td><td>{len(row["supported_not_published"])}</td></tr>')
parts+=['</table><p>Primary assessment covers issued supported criticisms. The separately rendered unresolved concerns above are counted but not judged in this condition; their author usefulness needs a separate assessment. Counts are native bundled items, not atomic precision or materiality. “Clean” concerns recorded prohibited access, not correctness or complete independence. The nonpublished supported column uses verifier/status labels, not independently established truth; merged IDs can repeat the same issue.</p>','<h2>Whole-report preference conditions</h2><p>Two orders per comparison; no pooling across families or protocols. Labels are hidden, but formats can reveal origin. Pipeline criticisms have passed an Opus verifier; plain criticisms have no equivalent filter, so support proportions are not comparable. Opus has a risk of preference for text it verified/reconciled; Sol generated both AI arms. Human reports are full prose whereas AI text is criticism-focused, and only Opus supplies human comparisons. Human reports are comparators, not truth labels.</p>']
for dirname,protocol,label in [('comparisons-v4','development-criticism-comparison-v4','Repaired v4: visual, genre and remedy restraint'),('comparisons','development-criticism-comparison-v3','Original v3: historical sensitivity condition')]:
 parts.append(f'<h3>{E(label)}</h3><table><tr><th>Case / judge</th><th>Contrast</th><th>Order-specific preference</th></tr>')
 for p in sorted((ROOT/dirname).glob('*/*/*.json')):
  d=read(p)
  if d.get('protocol')!=protocol:
   summary['errors'].append({'artifact':str(p),'reason':'Unexpected comparison protocol'});continue
  if final_ready:
   if dirname=='comparisons-v4':
    expected=comparison_audit[(d['case'],d['model'],d['left'],d['right'])]
    if sha(p)!=expected['artifact_sha256']:raise ValueError('Comparison changed since final provenance audit')
   elif sha(p)!=legacy_audit[str(p)]:raise ValueError('Historical comparison changed since audit')
  votes=[d['left'] if j['winner']=='candidate' else d['right'] if j['winner']=='reference' else 'tie' for j in d['judgments']]
  row={'case':d['case'],'model':d['model'],'protocol':protocol,'backend_version':d['backend_version'],'left':d['left'],'right':d['right'],'order_votes':votes,'invalid':d['invalid'],'source_hashes':d['source_hashes'],'order_rationales':[{'order':j['order'],'preference':votes[i],'rationale':j['judgment']['rationale']} for i,j in enumerate(d['judgments'])]}
  summary['comparisons'].append(row)
  if d['invalid']:summary['errors'].append({'artifact':str(p),'reason':'Invalid comparison judgments','details':d['invalid']})
  notes=''.join('<p><strong>'+E(x['order'])+' / '+E(x['preference'])+'</strong>: '+E(x['rationale'])+'</p>' for x in row['order_rationales'])
  parts.append(f'<tr><td>{E(d["case"])} / {E(d["model"])}</td><td>{E(d["left"])} vs {E(d["right"])}</td><td>{E("; ".join(votes))}{" — INVALID" if d["invalid"] else ""}<details><summary>Order-specific model reasoning (unadjudicated)</summary>{notes}</details></td></tr>')
 parts.append('</table>')
parts+=['<h2>Blinded full-criticism scrutiny</h2><p>V2 shares identical complete presentations once and retains all native origins. Near-duplicates can remain. Items are evaluated in pooled calls and may influence each other; these are not independent criticism judgments. Full claims and rationales remain untrusted; proposed remedies are assessed separately. Native formats and pre-verification filters differ. Exact quote bookkeeping applies only to claim labels and does not prove an inference. Rationale, consequence and remedy labels remain unchecked model opinions. Plain items lack separate rationales/remedies; only verifier-supported pipeline remedies are shown, so these labels cannot be compared across arms. Raw and checked claim labels are shown separately.</p>']
for entry in LAUNCH['inputs']:
 case=entry['case'];models=['claude-opus-5-5','gpt-6.1-sol']
 use_v2=any((ROOT/'criticism-assessments-v2'/model/f'{case}.json').exists() for model in models)
 if final_ready and not use_v2:raise ValueError('Final rendering cannot mix v1 into v2 cases')
 condition='deduplicated v2' if use_v2 else 'original v1, offline-rederived quote bookkeeping where available'
 judges={};overview={};packet=None;origins=None;provenance=None
 for model in models:
  if use_v2:
   p=ROOT/'criticism-assessments-v2'/model/f'{case}.json'
  else:
   p=ROOT/'criticism-assessments-rederived'/model/f'{case}.json'
   if not p.exists():p=ROOT/'criticism-assessments'/model/f'{case}.json'
  if not p.exists():
   summary['errors'].append({'case':case,'model':model,'reason':'Missing judge artifact','expected':str(p)})
   if final_ready and (case,model) not in {(x['case'],x['model']) for x in prov['partial_diagnostics']}:raise ValueError('Final rendering cannot hide an undeclared missing judge')
   continue
  d=read(p)
  if 'assessments' not in d:
   summary['errors'].append({'artifact':str(p),'reason':d.get('error','No valid criticism assessments')});continue
  if use_v2:
   if final_ready:
    expected=native_audit[(case,model)]
    if sha(p)!=expected['artifact_sha256'] or d['raw_judge_sha256']!=expected['raw_judge_sha256'] or d['packet_sha256']!=expected['packet_sha256']:raise ValueError('Native assessment changed since final provenance audit')
   snap=Path(d['packet_snapshot'])
   if sha(snap)!=d['packet_sha256']:raise ValueError('Changed immutable packet snapshot')
   candidate_packet=read(snap);candidate_origins=d['origins'];candidate_provenance=d['packet_provenance']
   if candidate_provenance['origins']!=candidate_origins:raise ValueError('Origin map differs from bound provenance')
   if sha(Path(d['raw_judge_artifact']))!=d['raw_judge_sha256']:raise ValueError('Changed raw judge result')
  else:
   if 'rederivation' in d and sha(Path(d['rederivation']['original_artifact']))!=d['rederivation']['original_sha256']:raise ValueError('Historical v1 artifact changed after rederivation')
   candidate_packet=read(ROOT/'criticism-packets'/f'{case}.json')
   candidate_provenance=read(ROOT/'criticism-packets'/f'{case}.origins.json')
   candidate_origins={i:[x] for i,x in candidate_provenance['origins'].items()}
  if packet is not None and (candidate_packet!=packet or candidate_origins!=origins):raise ValueError('Judge packet/origin mismatch')
  packet,origins,provenance=candidate_packet,candidate_origins,candidate_provenance
  for arm,digest in d['source_hashes'].items():
   if sha(ROOT/'reviews'/arm/case/'review.json')!=digest:raise ValueError('Assessment is tied to a different archived review')
  judges[model]={x['item_id']:x for x in d['assessments']}
  overview[model]={k:d.get(k) for k in ['groups','missed_material_questions','overall_qualified_assessment']}
  for arm in ['plain','holistic','audit']:
   rows=[r for r in d['assessments'] if any(o['arm']==arm for o in origins[r['item_id']])]
   summary['criticism_counts'].append({'case':case,'model':model,'condition':condition,'arm':arm,'n_native_items':len(rows),'raw_claim_model_labels':dict(Counter(r.get('raw_claim_status',r['claim_status']) for r in rows)),'quote_checked_claim_model_labels':dict(Counter(r['claim_status'] for r in rows)),'quote_check_only_differences':sum(r.get('raw_claim_status',r['claim_status'])!=r['claim_status'] for r in rows),
                                    'failed_quote_checks':sum(not r.get('quote_check_passed', not r.get('unmatched_evidence') and (r.get('raw_claim_status',r['claim_status'])=='unresolved' or bool(r.get('matched_supporting_evidence') if r.get('raw_claim_status',r['claim_status'])=='supported' else r.get('matched_counterevidence')))) for r in rows),'rationale_model_labels':dict(Counter(r['rationale_status'] for r in rows)),'remedy_model_labels':dict(Counter(r['remedy_status'] for r in rows))})
 if not judges:continue
 summary['packet_provenance'][case]={'condition':condition,**provenance}
 parts.append(f'<h3>{E(case)} · {E(condition)}</h3>')
 if use_v2:
  parts.append(f'<p>{provenance["n_native_items"]} native arm items; {provenance["n_unique_presentations"]} unique complete presentations. Audit inherited: {E(str(provenance["audit_inherited_ids"]))}. New audit: {E(str(provenance["audit_new_ids"]))}.</p>')
  parts.append('<details><summary>Nested editorial differences, near-duplicates and exclusions</summary><pre>'+E(json.dumps({k:provenance[k] for k in ['holistic_not_published_in_audit','nested_comparison_unavailable_reason','same_id_unmerged_presentations','excluded','unconfirmed_author_visible_excluded','legacy_unassessed_remedies']},indent=2))+'</pre></details>')
 if use_v2:
  strata={}
  for model,judgments in judges.items():
   groups={label:[] for label in ['plain_only','shared_nested','holistic_only','audit_only','other']}
   for id_,native in origins.items():
    arms={o['arm'] for o in native}
    label='plain_only' if arms=={'plain'} else 'shared_nested' if arms=={'holistic','audit'} else 'holistic_only' if arms=={'holistic'} else 'audit_only' if arms=={'audit'} else 'other'
    groups[label].append(id_)
   pairs=[]
   for native_id,members in provenance['same_id_unmerged_presentations'].items():
    ids=sorted({i for i,a in members});labels={i:{k:judgments[i].get(k) for k in ['raw_claim_status','rationale_status','remedy_status']} for i in ids}
    pairs.append({'native_id':native_id,'presentations':labels,'label_difference':len({json.dumps(v,sort_keys=True) for v in labels.values()})>1,'limits':'Within-call consistency diagnostic; evidence differs and these are not distinct scientific issues.'})
   strata[model]={'strata':{label:{'unique_presentations':len(ids),'raw_claim_model_labels':dict(Counter(judgments[i].get('raw_claim_status',judgments[i]['claim_status']) for i in ids)),'ids':ids} for label,ids in groups.items()},'same_id_unmerged_consistency':pairs,'limits':'Shared complete presentations judged once, attributed to both arms; not independent judgments or atomic correctness.'}
  summary.setdefault('native_strata',{})[case]=strata
  parts.append('<details><summary>Shared, broad-only and audit-only presentations; same-ID consistency</summary><pre>'+E(json.dumps(strata,indent=2))+'</pre></details>')
 summary.setdefault('judge_overviews',{})[case]=overview
 parts.append('<details><summary>Provisional groups, suggested missed questions and qualified model overview</summary><p>Unadjudicated model suggestions; not a completeness inventory.</p><pre>'+E(json.dumps(overview,indent=2))+'</pre></details>')
 for item in packet['criticisms']:
  id_=item['item_id'];native_origins=origins[id_];raw={m:rs[id_].get('raw_claim_status',rs[id_]['claim_status']) for m,rs in judges.items()};checked={m:rs[id_]['claim_status'] for m,rs in judges.items()}
  if len(set(raw.values()))>1 or len(set(checked.values()))>1:
   summary['disagreements'].append({'case':case,'item_id':id_,'condition':condition,'origins':native_origins,'claim':item['claim'],'raw_labels':raw,'checked_labels':checked,'bookkeeping_only':len(set(raw.values()))==1 and len(set(checked.values()))>1})
  arms=', '.join(o['arm'] for o in native_origins)
  parts.append(f'<details><summary>{E(arms)} / {E(id_)}: {E(item["claim"][:220])}</summary><p><strong>Full claim:</strong> {E(item["claim"])}</p>')
  if item.get('rationale'):parts.append('<p><strong>Rationale:</strong> '+E(item['rationale'])+'</p>')
  if item.get('remedy'):parts.append('<p><strong>Proposed response:</strong> '+E(item['remedy'])+'</p>')
  for model,rows in judges.items():
   row=rows[id_]
   parts.append(f'<p><strong>{E(model)}:</strong> raw claim {E(row.get("raw_claim_status",row["claim_status"]))}; quote-checked {E(row["claim_status"])}; rationale {E(row["rationale_status"])}; remedy {E(row["remedy_status"])}; consequence {E(row["consequence"])}.</p><p>{E(row["reasoning"])}</p><p><small>{E(row["limits"])}</small></p>')
  parts.append('</details>')
summary['partial_diagnostics']=[]
for p in (ROOT/'partial-criticism-assessments-v2').glob('*/*.json'):
 d=read(p)
 if final_ready:
  expected=next(x for x in prov['partial_diagnostics'] if (x['case'],x['model'])==(d['case'],d['model']))
  if sha(p)!=expected['artifact_sha256']:raise ValueError('Partial diagnostic changed since audit')
 summary['partial_diagnostics'].append({'artifact':str(p),'artifact_sha256':sha(p),'case':d['case'],'model':d['model'],'condition':d['condition'],'assessments':len(d['assessments']),'ungrouped_ids':d['ungrouped_ids'],'input_association':d['input_association'],'excluded_from_primary_protocol':True})
 parts.append('<h2>Explicit partial diagnostic: '+E(d['case'])+' / '+E(d['model'])+'</h2><p>'+E(d['condition'])+'. '+E(d['input_association'])+'. Ungrouped IDs: '+E(str(d['ungrouped_ids']))+'. These 82 well-formed item assessments are outside primary counts; no groups invented.</p><details><summary>Retained partial model opinions and incomplete groups</summary><pre>'+E(json.dumps(d,indent=2))+'</pre></details>')
parts+=['<h2>Controls and their limits</h2><p>Controls are protocol probes, not scientific precision. The initial five scored fields include easy explicit cues. Mixed external-source probes have mistaken expected labels: an absent manuscript misstatement or invalid cross-dataset transfer can be rejected without inspecting the source. Retain these as probe-design errors, not judge errors. The source-only follow-up was designed after those outputs and is weaker calibration evidence. The later figure probe omits the explicit “no pixels” rationale.</p>','<table><tr><th>Condition / judge / item</th><th>Expected and observed</th><th>Scored result</th></tr>']
for filename,label in [('assessor-control-results.json','Initial five scored fields'),('assessor-control-results-extended.json','Mixed source probe: expectation design error'),('assessor-control-results-followup.json','Mixed transfer probe: expectation design error; false-rationale and harder figure fields'),('assessor-source-only-results.json','Source-only post-hoc follow-up')]:
 p=ROOT/filename
 if not p.exists():continue
 d=read(p);summary['controls'].append({'condition':label,'artifact_sha256':sha(p),**d})
 for x in d['results']:
  actual=x.get('actual') or {'raw_claim_status':x.get('raw_claim_status'),'quote_checked_claim_status':x.get('checked_claim_status')}
  score=x.get('passes_raw',x.get('passes'))
  parts.append(f'<tr><td>{E(label)} / {E(x["model"])} / {E(x.get("item_id","source-count"))}</td><td>{E(str(x["expected"]))} → {E(str(actual))}</td><td>{E(str(score))}</td></tr>')
parts+=['</table>','<h2>Resource and completion diagnostics</h2><p>Stage durations omit some screening time and pending/failed time. Cached stages add zero new stage time; their original tool calls can still appear in traces. Retained timeouts are not free. Wall time is not an API charge, and this is not a matched-compute experiment.</p><table><tr><th>Case / arm</th><th>New recorded stage minutes</th><th>Cached stages</th><th>Retained partial attempts</th></tr>']
for entry in LAUNCH['inputs']:
 case=entry['case']
 for arm in ['plain','holistic','audit']:
  p=ROOT/'reviews'/arm/case/'review.json'
  if not p.exists():continue
  d=read(p);stages=d.get('stages',[]);seconds=sum(x.get('duration_seconds') or 0 for x in stages if x.get('status')!='cached')
  row={'case':case,'arm':arm,'new_stage_seconds':seconds,'cached_stages':[x['name'] for x in stages if x.get('status')=='cached'],'retained_partial_attempts':[x.name for x in p.parent.glob('review.partial-attempt-*.json')]}
  summary['resource_diagnostics'].append(row)
  elapsed='partial: elapsed time incomplete' if d.get('partial') else f'{seconds/60:.1f}'
  parts.append(f'<tr><td>{E(case)} / {E(arm)}</td><td>{E(elapsed)}</td><td>{E(", ".join(row["cached_stages"]) or "none")}</td><td>{E(", ".join(row["retained_partial_attempts"]) or "none")}</td></tr>')
parts.append('</table>')
parts.append('<h3>Generation wall time, including attempts</h3><table><tr><th>Case / mode</th><th>Elapsed minutes</th><th>Attempts / exits</th></tr>')
for p in sorted((ROOT/'generation').glob('*.json')):
 d=read(p);attempts=d['attempts'];seconds=sum(x['seconds'] for x in attempts)
 summary['generation_wall_diagnostics'].append({'job':p.stem,'seconds':seconds,'attempts':len(attempts),'returncodes':[x['returncode'] for x in attempts],'limits':'Whole sequential pipeline includes broad and audit arms; not audit-only compute or an API charge'})
 parts.append(f'<tr><td>{E(p.stem)}</td><td>{seconds/60:.1f}</td><td>{len(attempts)} / {E(str([x["returncode"] for x in attempts]))}</td></tr>')
parts.append('</table>')
for p in sorted(ROOT.glob('*status-*.json')):
 d=read(p)
 if d.get('errors'):summary['errors'].append({'artifact':str(p),'errors':d['errors']})
for dirname in ['comparisons','comparisons-v4']:
 for p in (ROOT/dirname).glob('*/*/history/*.json'):
  d=read(p)
  summary.setdefault('comparison_history',[]).append({'artifact':str(p),'artifact_sha256':sha(p),'condition':dirname,'case':d.get('case'),'model':d.get('model'),'left':d.get('left'),'right':d.get('right'),'invalid':d.get('invalid'),'cache_key':d.get('cache_key'),'limits':'Archived artifact may be cache reuse rather than another model call; internal CLI/schema repairs are not fully enumerated.'})
  if d.get('invalid'):summary['errors'].append({'artifact':str(p),'reason':'Historical invalid whole-report response','details':d['invalid']})
for dirname in ['criticism-assessments','criticism-assessments-v2']:
 files=list((ROOT/dirname).glob('*/*.invalid.json'))+list((ROOT/dirname).glob('*/history/*.invalid-*.json'))
 unique={}
 for p in sorted(files,key=lambda p:p.stat().st_mtime_ns):
  unique.setdefault((p.parent.parent.name if p.parent.name=='history' else p.parent.name,p.name.split('.invalid')[0],sha(p)),p)
 for (model,case,body_sha),p in unique.items():
  valid=ROOT/dirname/model/(case+'.json')
  summary['errors'].append({'artifact':str(p),'artifact_sha256':body_sha,'case':case,'model':model,'reason':'Invalid historical criticism response','superseded_by_valid':valid.exists() and valid.stat().st_mtime>p.stat().st_mtime})
 if dirname=='criticism-assessments-v2':
  for entry in LAUNCH['inputs']:
   for model in ['claude-opus-5-5','gpt-6.1-sol']:
    valid=ROOT/dirname/model/(entry['case']+'.json')
    if not valid.exists():continue
    d=read(valid);invalid=[(key,p) for key,p in unique.items() if key[:2]==(model,entry['case'])]
    recovered=next((x for x in summary['additional_recoveries'] if x['case']==entry['case'] and x['returncode']==0),None)
    accepted_source='logged additional recovery' if recovered and model=='gpt-6.1-sol' else 'frozen campaign'
    record={'case':entry['case'],'model':model,'retained_distinct_invalid_responses':[{'artifact':str(p),'sha256':key[2]} for key,p in invalid],'accepted_attempt_source':accepted_source,'accepted_raw_judge_sha256':d['raw_judge_sha256'],'limits':'Grouping-conditional acceptance; earlier complete item assessments are excluded from primary protocol results. Archive order is retention order, and identical bodies may deduplicate. CLI failures without a structured body remain in stage logs/completion records.'}
    if recovered and model=='gpt-6.1-sol':
     association_path=ROOT/('assessment-v2-'+entry['case']+'-recovery-association.json')
     if association_path.exists():
      association=read(association_path);record['recovery_association']=association
      if association['accepted_raw_judge_sha256']!=d['raw_judge_sha256']:raise ValueError('Recovery is tied to a different accepted raw sample')
     elif final_ready:raise ValueError('Additional recovery lacks accepted raw-call association')
    accepted={x['item_id']:x['claim_status'] for x in read(Path(d['raw_judge_artifact']))['result']['assessments']}
    repeats=[]
    for key,p in invalid:
     old=read(p);ids=[x['item_id'] for x in old['assessments']]
     complete=set(ids)==set(accepted) and len(ids)==len(accepted)
     changed=[{'item_id':x['item_id'],'invalid_attempt_label':x['claim_status'],'accepted_label':accepted[x['item_id']]} for x in old['assessments'] if x['item_id'] in accepted and x['claim_status']!=accepted[x['item_id']]]
     repeats.append({'invalid_artifact_sha256':key[2],'complete_assessment_inventory':complete,'claim_label_changes':changed,'limits':'Within-judge repeatability after a grouping failure; not correctness, independent replication or pipeline quality.'})
    record['retained_repeat_label_comparison']=repeats
    summary.setdefault('native_judge_attempts',[]).append(record)
parts.append('<details><summary>Native judge attempts and retained repeat-label differences</summary><pre>'+E(json.dumps(summary.get('native_judge_attempts',[]),indent=2))+'</pre></details>')
audit_path=ROOT/'assessment-provenance-audit.json'
if audit_path.exists():
 summary['provenance_audit']=read(audit_path)
 parts.append('<h2>Offline provenance audit</h2><p>'+E(summary['provenance_audit']['status'])+'</p><details><summary>Snapshot, packet, raw-call and complete prompt checks</summary><pre>'+E(json.dumps(summary['provenance_audit'],indent=2))+'</pre></details>')
parts.append('<details><summary>Retained whole-report comparison history (cache archives are not necessarily new calls)</summary><pre>'+E(json.dumps(summary.get('comparison_history',[]),indent=2))+'</pre></details>')
parts.append('<h2>Errors, exclusions and completion</h2><pre>'+E(json.dumps({'completion':completion,'additional_recoveries':summary['additional_recoveries'],'issues':summary['errors']},indent=2))+'</pre>')
checks=[]
for p in sorted((ROOT/'preflight').glob('*check.json')):
 checks.append({'artifact':str(p),'sha256':sha(p),'record':read(p)})
for name in ['satrevik-summary-arithmetic.json','quote-boundary-generation-impact.json','reproducible-numerical-checks.json']:
 p=ROOT/'preflight'/name
 if p.exists():checks.append({'artifact':str(p),'sha256':sha(p),'record':read(p)})
summary['targeted_checks']=checks
parts.append('<h2>Targeted source, arithmetic and anchoring checks</h2><p>These are post-hoc checks by the assessing agent, not random sampling, expert adjudication or an accuracy estimate. Each conclusion is shown with its own assumptions, defeaters and provenance; frozen decisions are unchanged.</p>')
for x in checks:
 d=x['record'];conclusion=d.get('bounded_assessment') or d.get('qualification') or d.get('bounded_conclusion') or d.get('limits') or d.get('method')
 parts.append('<details><summary>'+E(Path(x['artifact']).name)+'</summary><p>'+E(str(conclusion))+'</p><pre>'+E(json.dumps(d,indent=2))+'</pre></details>')
parts+=['<h2>Remaining scientific assessment</h2><p>Qualified assessors must adjudicate disputed and high-impact claims, whole rationales, remedy burden and unique audit contributions with complete primary sources and inspectable image evidence. Build an expert-checked atomic inventory alongside a reproducible sample; repeat generation to estimate variance and compare added audit compute with equally costly broad reading. Choose an independent corpus after development. Neither engineering checks nor these model opinions establishes an improvement in scientific review quality.</p></html>']
(ROOT/'assessment-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
OUT.mkdir(exist_ok=True);temporary=OUT/'assessment.tmp';temporary.write_text('\n'.join(parts));temporary.replace(OUT/'assessment.html')
print('Updated report:',len(summary['reports']),'reports,',len(summary['comparisons']),'protocol-labelled comparisons,',len(summary['criticism_counts']),'criticism strata')
