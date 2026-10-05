"""One explicit additional recovery attempt under unchanged frozen v2 conditions."""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;METHOD=json.loads((ROOT/'assessment-method-v2.json').read_text());CODE=Path(METHOD['code'])
ENV={k:v for k,v in os.environ.items() if k not in {'ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','OPENAI_API_KEY','LC_ALL'}};ENV['PYTHONPATH']=str(CODE/'src');ENV['PATH']='/home/lukas/.local/bin:/usr/local/bin:/usr/bin:/bin'
command=['/home/lukas/Documents/Coding/coarse-socpsy/.venv/bin/python',str(CODE/'eval/assess_criticisms.py'),'--root',str(ROOT),'--cases','niemeyer']
started=time.time()
with (ROOT/'assessment-v2-niemeyer-additional-recovery.log').open('w') as log:
 log.write(json.dumps({'at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'command':command,'purpose':'Third attempt after two complete assessment inventories but incomplete group membership; unchanged protocol, prompt, packet, schema, backend and source inputs. Existing Opus raw cache reused; no generation rerun.'})+'\n');log.flush()
 p=subprocess.run(command,cwd=CODE,env=ENV,stdout=log,stderr=subprocess.STDOUT)
record={'case':'niemeyer','command':command,'returncode':p.returncode,'seconds':time.time()-started,'attempt_after_original_two':True,'code_sha256':METHOD['code_sha256'],'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':'Additional conditionally accepted judge sample, not an independent replicate or pipeline rerun. Prior invalid responses remain archived.'}
(ROOT/'assessment-v2-niemeyer-additional-recovery.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(p.returncode)
