"""Prepare a fresh, isolated eighth-lesson Compose deployment on CLab."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway-env', type=Path, required=True)
    parser.add_argument('--project', default='campusclaw-week08-20261104')
    parser.add_argument('--port', type=int, default=18088)
    parser.add_argument('--rabbitmq-image', default='', help='Optional registry mirror or pinned digest')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if (root / '.env').exists() or root == args.gateway_env.resolve().parent:
        raise RuntimeError('Use a fresh source copy; never overwrite an existing private configuration')
    if not 1024 <= args.port <= 65535 or not args.project.startswith('campusclaw-week08-'):
        raise ValueError('Invalid isolated project or port')
    if any(c.isspace() for c in args.rabbitmq_image): raise ValueError('Invalid image reference')
    settings = {}
    allowed = {'EMBEDDING_BASE_URL', 'EMBEDDING_API_KEY', 'EMBEDDING_MODEL', 'EMBEDDING_DIM',
               'CHAT_MODEL', 'PYTHON_IMAGE', 'QDRANT_IMAGE'}
    for line in args.gateway_env.read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator and key in allowed: settings[key] = value.strip().strip('\"\'')
    if not settings.get('EMBEDDING_API_KEY'): raise RuntimeError('Gateway key is not configured')
    settings.update(COMPOSE_PROJECT_NAME=args.project, SECRET_KEY=secrets.token_hex(32),
        MCP_AUTH_TOKEN=secrets.token_hex(32), RABBITMQ_PASSWORD=secrets.token_hex(32),
        SEED_TEACHER_PASSWORD='teacher-test-password', SEED_STUDENT_A_PASSWORD='student-a-test-password',
        SEED_STUDENT_B_PASSWORD='student-b-test-password', APP_PORT=str(args.port))
    if args.rabbitmq_image: settings['RABBITMQ_IMAGE'] = args.rabbitmq_image
    fd = os.open(root / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(''.join(f'{key}={value}\n' for key, value in settings.items()))
    subprocess.run(['docker', 'compose', 'config', '-q'], cwd=root, check=True)
    subprocess.run(['docker', 'compose', 'up', '--build', '-d', '--wait'], cwd=root, check=True)
    print('Isolated week08 environment started on loopback port', args.port)


if __name__ == '__main__': main()
