"""Server-side origin checks and explicit untrusted-instruction boundaries."""
import re
import secrets
import unicodedata
from urllib.parse import urlsplit

from flask import jsonify, request, session

_INSTRUCTION = re.compile(
    r'忽略.{0,24}(此前|之前|指令|规则|评分)|绕过.{0,16}(权限|班级|限制)|'
    r'(输出|公开|泄露|逐字|展示).{0,16}(系统提示词|隐藏指令|内部评分)|'
    r'ignore.{0,24}(previous|instructions|rules)|'
    r'(reveal|print|disclose).{0,24}(system prompt|secret|credentials)', re.I | re.S)


def instruction_override(text):
    normalized = unicodedata.normalize('NFKC', text)
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Cf')
    return bool(_INSTRUCTION.search(normalized))


def origin_tuple(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
            return None
        if parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
            return None
        return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == 'https' else 80)
    except ValueError:
        return None


def init_security(app):
    def csrf_token():
        if '_csrf' not in session: session['_csrf'] = secrets.token_urlsafe(32)
        return session['_csrf']

    app.context_processor(lambda: {'csrf_token': csrf_token})

    @app.before_request
    def guard_origin():
        if request.method in {'GET', 'HEAD', 'OPTIONS'}:
            return None
        # Browsers supply Origin / Fetch Metadata on cross-site mutations. This
        # also covers login CSRF; non-browser clients retain their HTTP contract.
        origin = request.headers.get('Origin')
        if ((origin is not None and (origin_tuple(origin) is None or origin_tuple(origin) != origin_tuple(request.host_url)))
                or request.headers.get('Sec-Fetch-Site') == 'cross-site'):
            return jsonify(error='不允许跨来源写入'), 403
        if (request.mimetype == 'application/x-www-form-urlencoded' or request.path in {'/login', '/logout'}) and not request.headers.get('Authorization'):
            supplied = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token', '')
            expected = session.get('_csrf', '')
            if not expected or not secrets.compare_digest(supplied, expected):
                return jsonify(error='缺少有效的CSRF令牌'), 403
            session.pop('_csrf', None)
        return None
