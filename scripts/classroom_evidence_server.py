"""Loopback-only synthetic UI fixture. Does not validate RabbitMQ or the gateway."""
import argparse
import queue
import threading
import time
from pathlib import Path

from app.db import connect
from app.task_queue import dispatch_pending
from app.worker import process_task
from scripts.week05_evidence_server import make_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--port', type=int, default=18088)
    args = parser.parse_args()
    directory = Path(args.data_dir).resolve()
    app = make_app(directory, stub=True)

    def grade(context):
        time.sleep(2)
        return {'score': context['max_score'] * .8,
                'feedback': '本地测试替身：已读到提交正文与评分规程。请补充移项时的符号说明。'}

    app.config['GRADING_PROVIDER'] = grade
    messages = queue.Queue()

    class LocalBroker:
        def publish(self, identifier, dead=False):
            if not dead: messages.put(identifier)

    def local_worker():
        db = connect(app.config['DATABASE_PATH'])
        broker = LocalBroker()
        try:
            while True:
                dispatch_pending(db, broker)
                if (directory / 'consumer.enabled').exists():
                    try: identifier = messages.get_nowait()
                    except queue.Empty: pass
                    else: process_task(app, identifier)
                time.sleep(.1)
        finally:
            db.close()

    threading.Thread(target=local_worker, daemon=True).start()
    print('LOCAL FIXTURE: synthetic accounts, in-memory transport and deterministic grading; consumer paused.', flush=True)
    print('Enable consumer by creating consumer.enabled inside the data directory.', flush=True)
    app.run(host='127.0.0.1', port=args.port, threaded=True)


if __name__ == '__main__': main()
