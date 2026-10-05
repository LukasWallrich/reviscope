"""Compare frozen and repaired quotation anchoring offline; do not rewrite reviews."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import sys
from reviscope.verification import verify_quote


def audit(root):
    launch=json.loads((root/'launch.json').read_text())
    code=Path(launch['code'])
    frozen=runpy.run_path(str(code/'eval/run_known_errors.py'))
    if frozen['code_digest'](code)!=launch['code_sha256']:
        raise ValueError('Frozen generation code changed')
    spec=importlib.util.spec_from_file_location('reviscope.legacy_quote_impact',code/'src/reviscope/verification.py')
    legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)
    rows=[]
    for entry in launch['inputs']:
        for arm in ['holistic','audit']:
            path=root/'reviews'/arm/entry['case']/'review.json'
            if not path.exists():continue
            data=json.loads(path.read_text())
            if not any(s.get('kind')=='manuscript' and s.get('sha256')==entry['manuscript_sha256'] for s in data['sources']):
                raise ValueError('Archived review input differs from the submitted condition')
            for candidate in data['candidates']:
                for ev in candidate['evidence']:
                    before=legacy.verify_quote(ev['quote'],data['sources'],ev['source_id'])
                    after=verify_quote(ev['quote'],data['sources'],ev['source_id'])
                    if before.status==after.status:continue
                    finding=next((x for x in data['findings'] if x['id']==candidate['id']),{})
                    rows.append({'case':entry['case'],'arm':arm,'finding_id':candidate['id'],'quote':ev['quote'],
                                 'old_anchor':before.status,'new_anchor':after.status,'original_finding_status':finding.get('status'),
                                 'original_editorial_disposition':finding.get('editorial_disposition'),
                                 'review_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'rows':rows,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'unique_candidate_quotes':len({(x['case'],x['finding_id'],x['quote']) for x in rows}),
            'limits':'Post-hoc deterministic anchoring differences; not a lost-criticism count or counterfactual pipeline outcome. Frozen decisions unchanged; nested arms may repeat candidates.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    result=audit(args.root)
    path=args.root/'preflight/quote-boundary-generation-impact.json'
    path.write_text(json.dumps(result,indent=2)+'\n');print(len(result['rows']), 'arm occurrences;',result['unique_candidate_quotes'],'unique candidate quotations')
