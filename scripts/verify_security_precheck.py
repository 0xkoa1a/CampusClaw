"""Observe SEC01-04/07 on a disposable synthetic local app; no remediation."""
import argparse
import json
import tempfile
from pathlib import Path

from app.db import get_db
from scripts.week05_evidence_server import make_app


def verify(directory):
    app = make_app(directory, stub=True)
    anonymous, teacher, student, foreign = (app.test_client() for _ in range(4))
    for client, name, password in ((teacher, 'teacher_a', 'teacher-test-password'),
            (student, 'student_a1', 'student-a-test-password'),
            (foreign, 'student_b1', 'student-b-test-password')):
        assert client.post('/api/login', json={'username': name, 'password': password}).status_code == 200
    protected = ['/api/me', '/api/materials', '/api/agents', '/api/skills', '/api/conversations', '/api/assignments', '/api/tasks']
    sec01 = {url: anonymous.get(url).status_code for url in protected}
    material_id = app.extensions['week05_fixture']['material_ids'][0]
    sec02 = {
        'foreign_material': foreign.get(f'/api/materials/{material_id}').status_code,
        'foreign_download': foreign.get(f'/api/materials/{material_id}/file').status_code,
    }
    search = foreign.post('/api/search', json={'q': '方程', 'mode': 'keyword'})
    assert search.status_code == 200
    assert isinstance(search.json['hits'], list)
    sec02['foreign_search_no_a_material'] = str(material_id) not in {str(r['material_id']) for r in search.json['hits']}
    writes = {
        '/api/agents': {'name': '不应创建', 'role_prompt': 'test'},
        '/api/skills': {'source': '不应创建'},
        '/api/assignments': {'title': '不应创建', 'question': 'test'},
    }
    with app.app_context():
        before = {table: get_db().execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('agents', 'skills', 'assignments', 'grading_results')}
    sec03 = {url: student.post(url, json=body).status_code for url, body in writes.items()}
    # No public grading-result write endpoint exists. Browser bypass still hits server authorization.
    sec04 = {
        'direct_result_write': student.post('/api/tasks/fake/result', json={'score': 100}).status_code,
        'direct_assignment_write': sec03['/api/assignments'],
    }
    with app.app_context():
        after = {table: get_db().execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in before}
        audit_columns = [r['name'] for r in get_db().execute('PRAGMA table_info(mcp_audit)')]
    sec04['no_write_side_effect'] = before == after
    assert all(code == 401 for code in sec01.values())
    assert sec02 == {'foreign_material': 404, 'foreign_download': 404, 'foreign_search_no_a_material': True}
    assert all(code == 403 for code in sec03.values())
    assert sec04['direct_result_write'] == 404 and sec04['no_write_side_effect']
    for client in (teacher, student, foreign): client.post('/api/logout')
    return {
        'mode': 'local-synthetic-Flask-test-client', 'SEC01': sec01, 'SEC02': sec02,
        'SEC03': sec03, 'SEC04': sec04,
        'SEC07': {'observed': 'MCP audit schema', 'columns': audit_columns,
                  'missing_duration': 'duration_ms' not in audit_columns,
                  'missing_usage': 'usage' not in audit_columns,
                  'verdict': 'red: audit lacks duration and model usage; runtime log review pending'},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='campusclaw-security-') as directory:
        result = verify(directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('Local authorization checks passed; SEC07 red recorded. No real service audit claimed.')


if __name__ == '__main__': main()
