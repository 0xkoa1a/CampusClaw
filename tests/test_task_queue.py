"""Transport contract tests with a fake pika channel, not a real broker."""
import json
from types import SimpleNamespace

import pytest

from app.task_queue import BrokerUnavailable, RabbitBroker


class Channel:
    is_open = True

    def __init__(self, body=None):
        self.body = body
        self.events = []

    def basic_get(self, **kwargs):
        assert kwargs['auto_ack'] is False
        return SimpleNamespace(delivery_tag=7), None, self.body

    def basic_ack(self, **kwargs): self.events.append(('ack', kwargs))
    def basic_nack(self, **kwargs): self.events.append(('nack', kwargs))
    def basic_publish(self, **kwargs): self.events.append(('publish', kwargs)); return True


def broker(body=b'{"task_id":"task-1"}'):
    value = RabbitBroker('unused')
    value.channel = Channel(body)
    return value


def test_ack_occurs_after_successful_callback():
    value = broker()
    channel = value.channel
    assert value.consume_once(lambda identifier: channel.events.append(('commit', identifier)))
    assert channel.events == [('commit', 'task-1'), ('ack', {'delivery_tag': 7})]


def test_unhandled_callback_failure_nacks_for_redelivery():
    value = broker()
    channel = value.channel
    with pytest.raises(BrokerUnavailable):
        value.consume_once(lambda _: (_ for _ in ()).throw(RuntimeError('failure')))
    assert channel.events == [('nack', {'delivery_tag': 7, 'requeue': True})]


@pytest.mark.parametrize('body', [b'invalid', b'[]', b'{"task_id":12}', b'x' * 1025])
def test_malformed_messages_are_dead_lettered_without_execution(body):
    value = broker(body)
    channel = value.channel
    calls = []
    assert value.consume_once(calls.append)
    assert calls == []
    assert channel.events == [('nack', {'delivery_tag': 7, 'requeue': False})]


def test_persistent_message_contains_only_identifier():
    value = broker()
    value.publish('task-1')
    sent = value.channel.events[0][1]
    assert json.loads(sent['body']) == {'task_id': 'task-1'}
    assert sent['properties'].delivery_mode == 2
    assert sent['mandatory'] is True
    assert sent['routing_key'] == 'campusclaw.grading.v1'
