from conftest import login


def test_install_builtins_is_idempotent_and_preserves_edits(app, client):
    login(client)
    assert client.post('/api/platform/install').json == {'ok': True}
    agents = client.get('/api/agents').json['agents']
    assert len(agents) == 3
    assert len(client.get('/api/skills').json['skills']) == 2
    client.put(f"/api/agents/{agents[0]['id']}", json={'role_prompt': '教师改写的提示词'})
    assert client.post('/api/platform/install').status_code == 200
    again = client.get('/api/agents').json['agents']
    assert len(again) == 3
    assert again[0]['role_prompt'] == '教师改写的提示词'


def test_student_cannot_install_builtin_apps(client):
    login(client, 'student_a1', 'student-a-test-password')
    assert client.post('/api/platform/install').status_code == 403
