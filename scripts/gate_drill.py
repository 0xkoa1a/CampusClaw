"""Run a deliberate failing test and its repair in a disposable source copy."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/'reports/week10-local';output.mkdir(parents=True,exist_ok=True)
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).split(b'\0')
    with tempfile.TemporaryDirectory(prefix='campusclaw-gate-') as temporary:
        scratch=Path(temporary)
        for raw in paths:
            if not raw:continue
            relative=Path(raw.decode())
            if relative.name=='.env' or not (root/relative).is_file():continue
            dest=scratch/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/relative,dest)
        # Some safety tests expect a Git repository; no secrets or remote are configured.
        subprocess.run(['git','init','--quiet',str(scratch)],check=True)
        probe=scratch/'tests/test_gate_deliberate_regression.py'
        command=['make','check','PYTHON='+sys.executable]
        records=[]
        for phase,expected in [('red',200),('green',401)]:
            probe.write_text(f'def test_unauthenticated_request(client):\n    assert client.get("/api/me").status_code == {expected}\n')
            with (output/f'gate-{phase}.txt').open('w') as log:
                result=subprocess.run(command,cwd=scratch,stdout=log,stderr=subprocess.STDOUT)
            records.append({'phase':phase,'command':command,'exit_code':result.returncode,'expected_status':expected})
        assert records[0]['exit_code']!=0 and records[1]['exit_code']==0,records
    (output/'gate-drill.json').write_text(json.dumps({'mode':'disposable-copy-of-current-worktree','changed_file':'tests/test_gate_deliberate_regression.py','change':'expected unauthenticated status 200 -> 401','runs':records},indent=2)+'\n')
    print('make check: deliberate regression rejected, repaired expectation passed.')


if __name__=='__main__':main()
