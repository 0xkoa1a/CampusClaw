import io
import json

import pytest

from app.db import get_db
from app.gateway import GatewayUnavailable
from app.streaming import CitationFilter, sse_data, chat_stream
from app.vector import QdrantStore
from conftest import login


def setup_agent(app, client, skill=False):
    login(client)
    skill_ids = []
    if skill:
        source = "名称：数学解题引导\n适用条件：方程,数学\n工具：knowledge_search\n启用：是\n\n只指出下一步。"
        skill_ids = [client.post('/api/skills', json={'source': source}).json['skill']['id']]
    agent = client.post('/api/agents', json={'name': '数学助手', 'role_prompt': '帮助学生', 'skill_ids': skill_ids, 'material_ids': []}).json['agent']
    client.post('/api/logout')
    login(client, 'student_a1', 'student-a-test-password')
    identifier = client.post('/api/conversations', json={'agent_id': agent['id']}).json['conversation']['id']
    return agent, identifier


def events(response):
    return [(block.splitlines()[0][7:], json.loads(block.splitlines()[1][6:]))
            for block in response.data.decode().split('\n\n') if block]


def test_stream_no_evidence_history_and_citations(app, client):
    agent, cid = setup_agent(app, client, skill=True)
    calls = []
    def provider(messages):
        calls.append(messages)
        yield '检查'
        yield '括号[9'
        yield ']，下一步。'
    app.config['STREAM_PROVIDER'] = provider
    for index in range(5):
        result = events(client.post(f'/api/conversations/{cid}/messages', json={'content': f'方程第{index}轮', 'agent_id': 999, 'class_id': 2}))
        assert [x[0] for x in result] == ['meta', 'delta', 'delta', 'delta', 'done']
        assert result[0][1] == {'status': 'ungrounded', 'skill_name': '数学解题引导', 'citations': []}
        answer = ''.join(data['text'] for name, data in result if name == 'delta')
        assert answer == '检查括号，下一步。'
        with app.app_context():
            row = get_db().execute('SELECT * FROM messages WHERE id=?', (result[-1][1]['message_id'],)).fetchone()
            assert row['content'] == answer and row['status'] == 'complete'
        assert '不给最终答案' in calls[-1][0]['content']
        assert sum(f'方程第{index}轮' in m['content'] for m in calls[-1]) == 1
        assert len(calls[-1]) <= 7
    detail = client.get(f'/api/conversations/{cid}').json
    assert detail['conversation']['agent_id'] == agent['id']
    assert len(detail['messages']) == 10
    client.post('/api/logout')
    login(client, 'student_b1', 'student-b-test-password')
    assert client.get(f'/api/conversations/{cid}').json == client.get('/api/conversations/99999').json
    assert client.delete(f'/api/conversations/{cid}').status_code == 404


def test_failure_and_disconnect_save_partial_release_lock(app, client):
    _, cid = setup_agent(app, client)
    def failing(_):
        yield '已产生'
        raise GatewayUnavailable('upstream failed')
    app.config['STREAM_PROVIDER'] = failing
    result = events(client.post(f'/api/conversations/{cid}/messages', json={'content': '继续'}))
    assert result[-1][0] == 'error'
    detail = client.get(f'/api/conversations/{cid}').json
    assert detail['messages'][-1]['content'] == '已产生'
    assert detail['messages'][-1]['status'] == 'partial'
    closed = []
    def long(_):
        try:
            yield '片段一'
            yield '片段二'
        finally:
            closed.append(True)
    app.config['STREAM_PROVIDER'] = long
    response = client.post(f'/api/conversations/{cid}/messages', json={'content': '断连'}, buffered=False)
    iterator = iter(response.response)
    assert b'event: meta' in next(iterator)
    assert b'event: delta' in next(iterator)
    other = app.test_client()
    login(other, 'student_a1', 'student-a-test-password')
    assert other.post(f'/api/conversations/{cid}/messages', json={'content': '并发'}).status_code == 409
    assert other.delete(f'/api/conversations/{cid}').status_code == 409
    response.close()
    assert closed
    assert other.get(f'/api/conversations/{cid}').json['messages'][-1]['status'] == 'partial'
    assert other.delete(f'/api/conversations/{cid}').status_code == 204
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM messages WHERE conversation_id=?', (cid,)).fetchone()[0] == 0


def test_empty_upstream_emits_error_without_done(app, client):
    _, cid = setup_agent(app, client)
    app.config['STREAM_PROVIDER'] = lambda _: iter([])
    result = events(client.post(f'/api/conversations/{cid}/messages', json={'content': '继续'}))
    assert [item[0] for item in result] == ['meta', 'error']


def test_agent_disabled_existing_conversation_and_skill_toggle(app, client):
    agent, cid = setup_agent(app, client, skill=True)
    client.post('/api/logout')
    login(client)
    client.put(f"/api/agents/{agent['id']}", json={'enabled': False})
    source = client.get(f"/api/skills/{agent['skill_ids'][0]}").json['skill']['source_text']
    client.put(f"/api/skills/{agent['skill_ids'][0]}", json={'source': source.replace('启用：是', '启用：否')})
    client.post('/api/logout')
    login(client, 'student_a1', 'student-a-test-password')
    assert client.get('/api/agents').json == {'agents': []}
    assert client.post('/api/conversations', json={'agent_id': agent['id']}).status_code == 404
    app.config['STREAM_PROVIDER'] = lambda _: iter(['仍可回答'])
    result = events(client.post(f'/api/conversations/{cid}/messages', json={'content': '方程'}))
    assert result[0][1]['skill_name'] is None and result[-1][0] == 'done'


def test_scoped_keyword_and_vector_filter(app, client):
    from app.retrieval import keyword_search, vector_search
    with app.app_context():
        assert keyword_search('入门', 1, material_ids=[2]) == []
        assert keyword_search('入门', 1, material_ids=[1])[0]['material_id'] == 1
        assert vector_search('问题', 1, material_ids=[]) == []
    store = QdrantStore('http://unused', 'chunks', 2)
    captured = []
    store.ensure_collection = lambda: None
    def request(method, path, payload):
        captured.append(payload)
        return {'result': {'points': []}}
    store._request = request
    store.query([1, 0], 1, 4, material_ids=[1, 3])
    assert captured[0]['filter']['must'] == [{'key': 'class_id', 'match': {'value': 1}}, {'key': 'material_id', 'match': {'any': [1, 3]}}]


def test_bound_candidates_citations_and_preflight_outage(app, client):
    from app.indexing import index_material
    class Store:
        def __init__(self): self.points = {}
        def upsert(self, points): self.points.update({p['id']: p for p in points})
        def query(self, vector, class_id, limit, material_ids=None):
            return [{'id': p['id'], 'payload': p['payload'], 'score': .99} for p in self.points.values() if p['payload']['class_id'] == class_id and p['payload']['material_id'] in material_ids][:limit]
    store = Store()
    app.config.update(VECTOR_STORE=store, EMBEDDING_PROVIDER=lambda texts: [[1., 0.] for _ in texts])
    with app.app_context(): index_material(1, 1)
    agent, cid = setup_agent(app, client)
    client.post('/api/logout'); login(client)
    client.put(f"/api/agents/{agent['id']}", json={'material_ids': [1]})
    client.post('/api/logout'); login(client, 'student_a1', 'student-a-test-password')
    calls = []
    def provider(messages):
        calls.append(messages)
        yield '参考[1'
        yield ']，非法[99]。'
    app.config['STREAM_PROVIDER'] = provider
    result = events(client.post(f'/api/conversations/{cid}/messages', json={'content': '入门'}))
    assert result[0][1]['status'] == 'grounded'
    assert result[0][1]['citations'][0]['material_id'] == 1
    assert ''.join(data['text'] for name, data in result if name == 'delta') == '参考[1]，非法。'
    assert '材料《A 班' not in calls[0][0]['content']
    assert '材料《A 班' in calls[0][-1]['content']
    app.config['EMBEDDING_PROVIDER'] = lambda _: (_ for _ in ()).throw(GatewayUnavailable('offline'))
    assert client.post(f'/api/conversations/{cid}/messages', json={'content': '入门'}).status_code == 503
    assert client.delete(f'/api/conversations/{cid}').status_code == 204


@pytest.mark.parametrize('parts,count,expected', [(['甲[', '1]乙[9', ']'], 1, '甲[1]乙'), (['[1', ']无引用'], 0, '无引用'), (['普通[文字]', '[12'], 2, '普通[文字]')])
def test_citation_filter(parts, count, expected):
    cleaner = CitationFilter(count)
    assert ''.join(cleaner.feed(p) for p in parts) + cleaner.feed('', final=True) == expected


def test_upstream_sse_utf8_fragmented():
    data = 'data: {"choices":[{"delta":{"content":"中文"}}]}\r\n\r\ndata: [DONE]\n\n'.encode()
    class Chopped:
        def __init__(self): self.data = iter(bytes([b]) for b in data)
        def read(self, _): return next(self.data, b'')
    payloads = list(sse_data(Chopped()))
    assert json.loads(payloads[0])['choices'][0]['delta']['content'] == '中文'
    assert payloads[-1] == '[DONE]'


def test_real_client_requests_stream_and_closes_response(app, monkeypatch):
    data = 'data: {"choices":[{"delta":{"content":"好"},"finish_reason":null}]}\n\ndata: [DONE]\n\n'.encode()
    class Response(io.BytesIO):
        headers = {'Content-Type': 'text/event-stream'}
    response = Response(data)
    requests = []
    monkeypatch.setattr('app.streaming.urlopen', lambda req, timeout: (requests.append(req) or response))
    app.config.update(EMBEDDING_BASE_URL='https://test.invalid/v1', EMBEDDING_API_KEY='isolated-test-key')
    with app.app_context(): assert list(chat_stream([{'role': 'user', 'content': '测试'}])) == ['好']
    assert json.loads(requests[0].data)['stream'] is True
    assert response.closed
