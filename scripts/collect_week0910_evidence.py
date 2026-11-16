"""Allowlisted runtime metadata; run on CLab host with Docker access."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path('/home/ubuntu/workspace/campusclaw/verification/week10')


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=60).strip()


def collect():
    compose = ['docker', 'compose', '--project-directory', str(ROOT)]
    metadata = {}
    for service in ('app', 'worker', 'rabbitmq', 'qdrant', 'mcp-demo'):
        cid = run(*compose, 'ps', '-q', service)
        item = json.loads(run('docker', 'inspect', '--format',
            '{"image":{{json .Image}},"status":{{json .State.Status}},'
            '"health":{{with .State.Health}}{{json .Status}}{{else}}null{{end}},'
            '"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}}}', cid))
        metadata[service] = item
    code = '''import importlib.util,json,os,pathlib,sqlite3,urllib.request
db=sqlite3.connect('/app/data/campusclaw.sqlite3')
events=[]
for stamp,event,rid,uid,raw in db.execute("SELECT timestamp,event,request_id,user_id,fields_json FROM audit_events WHERE event IN ('skill_invocation','llm_usage','llm_stream_usage') ORDER BY id DESC LIMIT 20"):
 f=json.loads(raw)
 events.append({'timestamp':stamp,'event':event,'request_id':rid,'user_id':uid,**{k:f.get(k) for k in ('class_id','skill','status','duration_ms','usage')}})
print(json.dumps({'uid':os.getuid(),'project_py_files':len(list(pathlib.Path('/app').rglob('*.py'))),'private_env_present':pathlib.Path('/app/.env').exists(),'pip_importable':importlib.util.find_spec('pip') is not None,'ready':json.load(urllib.request.urlopen('http://127.0.0.1:8080/ready')),'skill_events':events},ensure_ascii=False))
'''
    probe = json.loads(run(*compose, 'exec', '-T', 'app', 'python', '-c', code))
    assert probe['uid'] != 0 and probe['project_py_files'] == 0
    assert not probe['private_env_present'] and not probe['pip_importable']
    assert all(item['status'] == 'running' for item in metadata.values())
    raw = json.loads((ROOT.parent.parent / 'archives/evidence/week10/mcp-rag-real.json').read_text())
    # Export counts and verdict only; full model traces remain on the isolated host.
    mcp = {k: raw[k] for k in ('status',) if k in raw}
    for key in ('checks', 'turns'):
        if key in raw:
            mcp[key + '_count'] = len(raw[key])
    return {'project':'campusclaw-week10-20261117','port':18100,
            'containers':metadata,'runtime_probe':probe,'mcp_regression':mcp}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=collect()
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Allowlisted runtime evidence saved.')
