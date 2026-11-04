"""RabbitMQ transport and outbox dispatcher; never publishes student content."""
import json
import time

from .task_store import recover_expired


class BrokerUnavailable(Exception):
    pass


class RabbitBroker:
    def __init__(self, url, queue='campusclaw.grading.v1'):
        self.url, self.queue, self.dead_queue = url, queue, queue + '.dead'
        self.connection = self.channel = None

    def connect(self):
        if self.channel is not None and self.channel.is_open: return
        if not self.url: raise BrokerUnavailable('RabbitMQ尚未配置')
        import pika
        try:
            parameters = pika.URLParameters(self.url)
            parameters.heartbeat, parameters.blocked_connection_timeout = 300, 10
            parameters.socket_timeout, parameters.connection_attempts = 5, 1
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.dead_queue, durable=True)
            self.channel.queue_declare(queue=self.queue, durable=True, arguments={
                'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': self.dead_queue})
            self.channel.basic_qos(prefetch_count=1)
            self.channel.confirm_delivery()
        except Exception as exc:
            self.close()
            raise BrokerUnavailable('RabbitMQ连接不可用') from exc

    def publish(self, task_id, dead=False):
        import pika
        try:
            self.connect()
            result = self.channel.basic_publish(exchange='', routing_key=self.dead_queue if dead else self.queue,
                body=json.dumps({'task_id': task_id}).encode(), mandatory=True,
                properties=pika.BasicProperties(delivery_mode=2, content_type='application/json', message_id=task_id))
            if result is False: raise BrokerUnavailable('RabbitMQ未确认消息')
        except Exception as exc:
            self.close()
            raise BrokerUnavailable('RabbitMQ消息发布未确认') from exc

    def consume_once(self, callback):
        try:
            self.connect()
            method, properties, body = self.channel.basic_get(queue=self.queue, auto_ack=False)
            if method is None:
                self.connection.process_data_events(time_limit=0)
                return False
            try:
                value = json.loads(body) if len(body) <= 1024 else None
                if not isinstance(value, dict) or not isinstance(value.get('task_id'), str) or len(value['task_id']) > 64:
                    raise ValueError('invalid queue message')
            except (ValueError, TypeError, UnicodeError):
                self.channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return True
            try:
                callback(value['task_id'])
            except Exception:
                self.channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                raise
            self.channel.basic_ack(delivery_tag=method.delivery_tag)
            return True
        except Exception as exc:
            self.close()
            raise BrokerUnavailable('消费者暂时无法完成消息') from exc

    def close(self):
        try:
            if self.connection is not None and self.connection.is_open: self.connection.close()
        except Exception:
            pass
        self.connection = self.channel = None


def dispatch_pending(db, broker, now=None):
    now = time.time() if now is None else now
    recover_expired(db, now)
    rows = db.execute('''SELECT o.task_id,o.generation,o.kind FROM task_outbox o JOIN grading_tasks t ON t.id=o.task_id
        WHERE o.published=0 AND o.available_at<=? AND (o.kind='dead' OR t.status='pending')
        ORDER BY o.available_at,o.task_id LIMIT 50''', (now,)).fetchall()
    count = 0
    for row in rows:
        broker.publish(row['task_id'], dead=row['kind'] == 'dead')
        with db:
            db.execute('''UPDATE task_outbox SET published=1,published_at=?
                WHERE task_id=? AND generation=?''', (now, row['task_id'], row['generation']))
        count += 1
    return count
