"""Trigger an actual sustained in-app alert in the explicit local fault fixture."""
import json
from pathlib import Path
import time
from urllib.request import Request,build_opener,ProxyHandler


def main():
    opener=build_opener(ProxyHandler({})); tokens=[]
    def call(method,path,body=None,token=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=Request('http://127.0.0.1:18091'+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
        with opener.open(req,timeout=10) as response:
            raw=response.read().decode()
            return raw if 'text/event-stream' in response.headers.get('Content-Type','') else json.loads(raw)
    def login(username,password):
        data=call('POST','/api/login',{'username':username,'password':password,'auth_mode':'bearer'})
        tokens.append(data['access_token']);return tokens[-1]
    teacher=login('teacher_a','teacher-test-password');student=login('student_a1','student-a-test-password')
    try:
        agents=call('GET','/api/agents',token=teacher)['agents']
        aid=next(a['id'] for a in agents if a['name']=='数学解题助手')
        cid=call('POST','/api/conversations',{'agent_id':aid},student)['conversation']['id']
        started=time.monotonic();failures=0
        while time.monotonic()-started<340:
            stream=call('POST',f'/api/conversations/{cid}/messages',{'content':'数学方程观测故障演练'},student)
            assert 'event: error' in stream
            failures+=1
            dashboard=call('GET','/api/monitoring?window=300',token=teacher)
            active=[a for a in dashboard['alerts'] if a['status']=='active' and a['skill']=='数学解题引导']
            if active:
                result={'mode':'local-stub-controlled-failure-real-HTTP','elapsed_seconds':time.monotonic()-started,'failed_invocations':failures,'policy':dashboard['alert_policy'],'notification':active[0],'delivery':'persisted in teacher in-app notification list'}
                output=Path('reports/week10-local/alert-trigger.json');output.parent.mkdir(parents=True,exist_ok=True)
                output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Sustained in-app alert triggered.',flush=True);return
            time.sleep(2)
        raise AssertionError('No actual sustained alert notification within configured window')
    finally:
        for token in tokens:call('POST','/api/logout',{},token)


if __name__=='__main__':main()
