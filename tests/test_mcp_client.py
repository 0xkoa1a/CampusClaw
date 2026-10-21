import io
import json

import pytest

from app.gateway import GatewayUnavailable
from app.mcp_client import discover, rpc


class Reply(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_args): self.close()


def fake_opener(monkeypatch, respond):
    class Opener:
        def open(self, request, timeout):
            assert timeout == 5
            body = json.loads(request.data)
            return Reply(respond(request, body))
    monkeypatch.setattr('app.mcp_client.build_opener', lambda *_args: Opener())


def test_rpc_auth_matching_id_and_no_proxy_redirect(monkeypatch):
    def respond(request, body):
        assert request.full_url == 'http://mcp-demo:8090/mcp'
        assert request.get_header('Authorization') == 'Bearer test-token'
        assert body['method'] == 'tools/call'
        return json.dumps({'jsonrpc': '2.0', 'id': body['id'], 'result': {'content': []}}).encode()
    fake_opener(monkeypatch, respond)
    assert rpc('http://mcp-demo:8090', 'test-token', 'tools/call') == {'content': []}


@pytest.mark.parametrize('raw', [b'not json', b'[]', b'x' * 65537,
    b'{"jsonrpc":"2.0","id":"wrong","result":{}}'])
def test_rpc_rejects_malformed_or_oversized_responses(monkeypatch, raw):
    fake_opener(monkeypatch, lambda *_args: raw)
    with pytest.raises(GatewayUnavailable): rpc('http://mcp-demo:8090', 'test-token', 'tools/list')


def test_discovery_validates_schema_and_version(monkeypatch):
    calls = []
    def respond(_request, body):
        calls.append(body['method'])
        result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}} if body['method'] == 'initialize' else {'tools': [
            {'name': 'calculate', 'description': '计算', 'inputSchema': {'type': 'object', 'properties': {}}}]}
        return json.dumps({'jsonrpc': '2.0', 'id': body['id'], 'result': result}).encode()
    fake_opener(monkeypatch, respond)
    assert discover('http://mcp-demo:8090', 'test-token')[0]['name'] == 'calculate'
    assert calls == ['initialize', 'tools/list']


def test_discovery_rejects_remote_schema_references(monkeypatch):
    def respond(_request, body):
        result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}} if body['method'] == 'initialize' else {'tools': [
            {'name': 'calculate', 'inputSchema': {'type': 'object', 'properties': {'x': {'$ref': 'http://example.com/schema'}}}}]}
        return json.dumps({'jsonrpc': '2.0', 'id': body['id'], 'result': result}).encode()
    fake_opener(monkeypatch, respond)
    with pytest.raises(GatewayUnavailable): discover('http://mcp-demo:8090', 'test-token')


def test_transport_timeout_is_reported_without_credentials(monkeypatch):
    class Opener:
        def open(self, *_args, **_kwargs): raise TimeoutError('private transport detail')
    monkeypatch.setattr('app.mcp_client.build_opener', lambda *_args: Opener())
    with pytest.raises(GatewayUnavailable, match='MCP 服务连接或协议错误') as error:
        rpc('http://mcp-demo:8090', 'test-only-secret', 'tools/list')
    assert 'test-only-secret' not in str(error.value)
