"""Class assignments and immediate, idempotent asynchronous acceptance."""
import math
import re

from flask import Blueprint, current_app, g, jsonify, render_template, request

from .agent_store import ApiProblem, missing
from .auth import require_user
from .db import get_db
from .openapi import api_doc
from .task_store import TASK_QUERY, accept_submission, override_grade, task_json

bp = Blueprint('assignments', __name__)


@bp.errorhandler(ApiProblem)
def problem(error): return jsonify(error=str(error)), error.status


def owned_assignment(identifier):
    row = get_db().execute('SELECT * FROM assignments WHERE id=? AND class_id=?', (identifier, g.user['class_id'])).fetchone()
    if row is None: raise missing()
    return row


def public_assignment(row):
    keys = ['id', 'title', 'question', 'max_score', 'skill_id', 'created_at']
    if g.user['role'] == 'teacher': keys += ['reference_answer', 'rubric']
    return {key: row[key] for key in keys}


@bp.get('/assignments')
def page():
    denied = require_user(page=True)
    return denied if denied else render_template('assignments.html')


ASSIGNMENT_BODY = {'required': True, 'content': {'application/json': {'schema': {
    'type': 'object', 'required': ['title', 'question'], 'properties': {
        'title': {'type': 'string', 'maxLength': 120}, 'question': {'type': 'string', 'maxLength': 4000},
        'reference_answer': {'type': 'string', 'maxLength': 2000}, 'rubric': {'type': 'string', 'maxLength': 2000},
        'max_score': {'type': 'integer', 'minimum': 1, 'maximum': 100}, 'skill_id': {'type': 'integer', 'nullable': True},
    }}}}}


@bp.route('/api/assignments', methods=['GET', 'POST'])
@api_doc({'get': {'summary': '列出本班课堂作业'}, 'post': {'summary': '教师创建作业', 'requestBody': ASSIGNMENT_BODY,
    'x-error-statuses': ['400', '403', '404'], 'x-success-status': 201}})
def assignments():
    denied = require_user()
    if denied: return denied
    db = get_db()
    if request.method == 'GET':
        return jsonify(assignments=[public_assignment(r) for r in db.execute('SELECT * FROM assignments WHERE class_id=? ORDER BY id DESC', (g.user['class_id'],))])
    if g.user['role'] != 'teacher': raise ApiProblem('需要教师权限', 403)
    data = request.get_json(silent=True)
    if not isinstance(data, dict): raise ApiProblem('需要JSON对象')
    fields = {}
    for key, limit in (('title', 120), ('question', 4000), ('reference_answer', 2000), ('rubric', 2000)):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > limit or (key in {'title', 'question'} and not value.strip()):
            raise ApiProblem(f'{key}不能为空或超过长度限制')
        fields[key] = value.strip()
    score, skill = data.get('max_score', 100), data.get('skill_id')
    if type(score) is not int or not 1 <= score <= 100: raise ApiProblem('max_score须为1–100的整数')
    if skill is not None:
        if type(skill) is not int or skill <= 0: raise ApiProblem('skill_id须为正整数')
        if not db.execute('SELECT 1 FROM skills WHERE id=? AND class_id=? AND enabled=1', (skill, g.user['class_id'])).fetchone(): raise missing()
    with db:
        identifier = db.execute('''INSERT INTO assignments(class_id,title,teacher_id,question,reference_answer,rubric,max_score,skill_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''', (g.user['class_id'], fields['title'], g.user['id'], fields['question'],
            fields['reference_answer'], fields['rubric'], score, skill)).lastrowid
    return jsonify(assignment=public_assignment(owned_assignment(identifier))), 201


@bp.get('/api/assignments/<int:identifier>')
@api_doc({'get': {'summary': '读取本班作业，学生不见参考答案', 'x-error-statuses': ['404']}})
def assignment(identifier):
    denied = require_user()
    return denied if denied else jsonify(assignment=public_assignment(owned_assignment(identifier)))


@bp.post('/api/assignments/<int:identifier>/submissions')
@api_doc({'post': {'summary': '学生提交，持久接收后立即返回202', 'x-error-statuses': ['400', '403', '404', '409'],
    'parameters': [{'name': 'Idempotency-Key', 'in': 'header', 'required': True, 'schema': {'type': 'string', 'maxLength': 128}}],
    'requestBody': {'required': True, 'content': {'application/json': {'schema': {'type': 'object', 'required': ['content'],
        'properties': {'content': {'type': 'string', 'maxLength': 4000}}}}}}, 'x-success-status': 202}})
def submit(identifier):
    denied = require_user()
    if denied: return denied
    if g.user['role'] != 'student': raise ApiProblem('仅学生可提交作业', 403)
    owned_assignment(identifier)
    key = request.headers.get('Idempotency-Key', '')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', key): raise ApiProblem('需要1–128字符的Idempotency-Key')
    data = request.get_json(silent=True)
    content = data.get('content') if isinstance(data, dict) else None
    if not isinstance(content, str) or not content.strip() or len(content) > 4000: raise ApiProblem('content须为1–4000字')
    result = accept_submission(identifier, g.user['class_id'], g.user['id'], content.strip(), key, current_app.config['TASK_MAX_ATTEMPTS'])
    return jsonify(result), 202


@bp.get('/api/tasks')
@api_doc({'get': {'summary': '只读列出可见批改任务，最多50条'}})
def tasks():
    denied = require_user()
    if denied: return denied
    condition, params = 't.class_id=?', [g.user['class_id']]
    if g.user['role'] != 'teacher': condition += ' AND t.user_id=?'; params.append(g.user['id'])
    return jsonify(tasks=[task_json(r) for r in get_db().execute(TASK_QUERY + ' WHERE ' + condition + ' ORDER BY t.created_at DESC,t.id DESC LIMIT 50', params)])


@bp.get('/api/tasks/<string:identifier>')
@api_doc({'get': {'summary': '读取任务状态与结构化批改结果', 'x-error-statuses': ['404']}})
def task(identifier):
    denied = require_user()
    if denied: return denied
    row = get_db().execute(TASK_QUERY + ' WHERE t.id=? AND t.class_id=?', (identifier, g.user['class_id'])).fetchone()
    if row is None or (g.user['role'] != 'teacher' and row['user_id'] != g.user['id']): raise missing()
    return jsonify(task=task_json(row))


@bp.put('/api/tasks/<string:identifier>/grade')
@api_doc({'put': {
    'summary': '教师覆盖本班批改结果',
    'description': '需要有效登录会话。仅教师可用；学生返回403。任务、提交和作业都必须属于教师会话中的班级，跨班或不存在的任务返回404。score须为有限数字且在0到作业满分之间（含边界）；feedback须为非空字符串且最多2000字。成功后结果来源为teacher-override，任务为succeeded，租约被清除。',
    'requestBody': {'required': True, 'content': {'application/json': {'schema': {
        'type': 'object', 'required': ['score', 'feedback'], 'additionalProperties': False,
        'properties': {
            'score': {'type': 'number', 'minimum': 0, 'description': '必须是有限数值，且不得超过该作业的max_score'},
            'feedback': {'type': 'string', 'minLength': 1, 'maxLength': 2000},
        }}}}},
    'x-error-statuses': ['400', '403', '404'], 'x-success-status': 200,
    'x-response-schema': {'type': 'object', 'required': ['task'], 'properties': {
        'task': {'type': 'object', 'required': ['id', 'status', 'result'], 'properties': {
            'id': {'type': 'string'}, 'status': {'type': 'string', 'enum': ['succeeded']},
            'result': {'type': 'object', 'required': ['score', 'feedback', 'source'], 'properties': {
                'score': {'type': 'number'}, 'feedback': {'type': 'string'},
                'source': {'type': 'string', 'enum': ['teacher-override']},
            }},
        }},
    }},
}})
def grade_task(identifier):
    denied = require_user()
    if denied: return denied
    if g.user['role'] != 'teacher': raise ApiProblem('需要教师权限', 403)
    db = get_db()
    task = db.execute('''SELECT t.id,a.max_score FROM grading_tasks t
        JOIN submissions s ON s.id=t.submission_id
        JOIN assignments a ON a.id=s.assignment_id
        WHERE t.id=? AND t.class_id=? AND s.class_id=? AND a.class_id=?''',
        (identifier, g.user['class_id'], g.user['class_id'], g.user['class_id'])).fetchone()
    if task is None: raise missing()
    data = request.get_json(silent=True)
    if not isinstance(data, dict): raise ApiProblem('需要JSON对象')
    score, feedback = data.get('score'), data.get('feedback')
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ApiProblem('score须为有限数字且在0到作业满分之间')
    try:
        finite = math.isfinite(score)
    except OverflowError:
        finite = False
    if not finite or not 0 <= score <= task['max_score']:
        raise ApiProblem('score须为有限数字且在0到作业满分之间')
    if not isinstance(feedback, str) or not feedback.strip() or len(feedback) > 2000:
        raise ApiProblem('feedback须为非空字符串且最多2000字')
    if not override_grade(db, identifier, g.user['class_id'], score, feedback): raise missing()
    row = db.execute(TASK_QUERY + ' WHERE t.id=? AND t.class_id=?', (identifier, g.user['class_id'])).fetchone()
    return jsonify(task=task_json(row))
