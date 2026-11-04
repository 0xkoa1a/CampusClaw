"""Measure the loopback fixture's HTTP acceptance; never certifies RabbitMQ."""
import argparse
import http.cookiejar
import json
import math
import time
import urllib.request
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    marker = args.data_dir / 'consumer.enabled'
    marker.unlink(missing_ok=True)
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.ProxyHandler({}))

    def request(route, body=None, key=None):
        headers = {'Content-Type': 'application/json'}
        if key: headers['Idempotency-Key'] = key
        req = urllib.request.Request('http://127.0.0.1:18088' + route,
            data=None if body is None else json.dumps(body).encode(), headers=headers)
        started = time.perf_counter()
        with client.open(req, timeout=10) as response:
            return response.status, json.load(response), time.perf_counter() - started

    request('/api/login', {'username': 'student_a1', 'password': 'student-a-test-password'})
    assignment = request('/api/assignments')[1]['assignments'][0]
    route = f"/api/assignments/{assignment['id']}/submissions"
    timings, task_ids = [], []
    prefix = uuid.uuid4().hex
    try:
        for number in range(20):
            code, body, seconds = request(route, {'content': '本地合成验收答案'}, prefix + str(number))
            assert code == 202 and body['status'] == 'pending' and 'result' not in body
            timings.append(seconds)
            task_ids.append(body['task_id'])
        replay = request(route, {'content': '本地合成验收答案'}, prefix + '0')[1]
        assert replay['replayed'] and replay['task_id'] == task_ids[0]
        assert request('/api/tasks/' + task_ids[0])[1]['task']['status'] == 'pending'
        marker.touch(mode=0o600)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            task = request('/api/tasks/' + task_ids[0])[1]['task']
            if task['status'] == 'succeeded': break
            time.sleep(.3)
        else: raise AssertionError('fixture consumer did not complete the first task')
        p95 = sorted(timings)[math.ceil(len(timings) * .95) - 1]
        assert p95 < 1, 'local fixture acceptance should not await the two-second provider'
        result = {'mode': 'local-memory-transport-and-test-provider', 'samples': 20,
            'response_seconds': timings, 'p95_seconds': p95, 'provider_delay_seconds': 2,
            'all_202_without_result': True, 'paused_pending': True, 'resumed_success': True,
            'same_key_same_task': True, 'task_id': task_ids[0], 'result_source': task['result']['source'],
            'real_broker_verdict': 'pending: durability, restart and broker redelivery untested'}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(f'Local fixture: 20 x 202, P95={p95:.4f}s; paused/resumed and duplicate acceptance passed.')
    finally:
        marker.touch(mode=0o600)
        request('/api/logout', {})


if __name__ == '__main__': main()
