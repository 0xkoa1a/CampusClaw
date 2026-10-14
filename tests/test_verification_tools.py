import subprocess
import sys
from pathlib import Path

from app import create_app
from scripts.week05_evidence_server import make_app


def test_apitest_direct_script_entrypoint_imports_package():
    script = Path(__file__).resolve().parents[1] / 'apitest/run_all.py'
    response = subprocess.run([sys.executable, str(script), '--base-url', 'https://external.invalid', '--database-path', '/nonexistent'], capture_output=True, text=True)
    assert response.returncode == 2
    assert 'ModuleNotFoundError' not in response.stderr


def test_fixture_restart_keeps_messages_and_configuration(tmp_path):
    from app.db import get_db
    app = make_app(tmp_path / 'fresh', stub=True)
    client = app.test_client()
    client.post('/api/login', json={'username': 'student_a1', 'password': 'student-a-test-password'})
    cid = client.post('/api/conversations', json={'agent_id': 1}).json['conversation']['id']
    response = client.post(f'/api/conversations/{cid}/messages', json={'content': '方程检查'})
    assert b'event: done' in response.data
    before = client.get(f'/api/conversations/{cid}').json
    config = {name: app.config[name] for name in ('DATABASE_PATH', 'UPLOAD_DIR', 'SECRET_KEY')}
    restarted = create_app(config)
    with restarted.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM agents').fetchone()[0] == 2
        assert get_db().execute('SELECT content FROM messages WHERE conversation_id=? AND role=?', (cid, 'assistant')).fetchone()[0] == before['messages'][-1]['content']
