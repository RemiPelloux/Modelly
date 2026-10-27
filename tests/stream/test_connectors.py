"""Tests for the MQTT and Kafka sources, with stand-in clients (modelly.stream.connectors).

No broker and no client library is needed: the sources take an injected
client, and the lazy imports are replaced by fake modules.
"""

import json
import sys
from types import SimpleNamespace

import pytest

from modelly.stream import KafkaSource, MQTTSource, connectors


class FakeMQTTClient:
    """Records what a paho ``Client`` would be asked to do."""

    def __init__(self, *args):
        """Remember the constructor arguments (the callback API version)."""
        self.args = args
        self.calls = []
        self.on_message = None

    def connect(self, host, port):
        """Note the broker address."""
        self.calls.append(("connect", host, port))

    def loop_start(self):
        """Note the network loop start."""
        self.calls.append(("loop_start",))

    def loop_stop(self):
        """Note the network loop stop."""
        self.calls.append(("loop_stop",))

    def disconnect(self):
        """Note the disconnection."""
        self.calls.append(("disconnect",))

    def subscribe(self, topic):
        """Note the subscription."""
        self.calls.append(("subscribe", topic))

    def deliver(self, payload):
        """Deliver ``payload`` (a JSON-able value) as the network thread would."""
        message = SimpleNamespace(payload=json.dumps(payload).encode())
        self.on_message(self, None, message)


class FakeMessage:
    """A Kafka message: a value or an error."""

    def __init__(self, value=None, error=None):
        """A message carrying ``value`` bytes, or ``error``."""
        self._value = value
        self._error = error

    def value(self):
        """The payload."""
        return self._value

    def error(self):
        """The error, or ``None``."""
        return self._error


class FakeConsumer:
    """A confluent-kafka consumer handing out queued batches."""

    def __init__(self, config=None):
        """Start with no batch queued."""
        self.config = config
        self.batches = []
        self.subscribed = None
        self.closed = False
        self.consumed = []

    def subscribe(self, topics):
        """Note the topics."""
        self.subscribed = topics

    def consume(self, num_messages, timeout):
        """The next queued batch, or nothing."""
        self.consumed.append((num_messages, timeout))
        return self.batches.pop(0) if self.batches else []

    def close(self):
        """Note the close."""
        self.closed = True


def _record(time, cases):
    """A JSON-encoded observation record."""
    return json.dumps({"time": time, "cases": cases}).encode()


def test_mqtt_messages_wait_for_the_next_poll():
    """Messages queue on arrival and come out of ``poll`` in time order, once."""
    client = FakeMQTTClient()
    source = MQTTSource("town/cases", client=client)
    assert client.calls == [("subscribe", "town/cases")]
    client.deliver({"time": 2, "cases": 5})
    client.deliver([{"time": 1, "cases": 3}, {"time": 3, "cases": 8}])
    assert [o.time for o in source.poll(until=2)] == [1.0, 2.0]
    assert [o.values["cases"] for o in source.poll()] == [8.0]
    assert source.poll() == []
    source.close()
    assert ("disconnect",) not in client.calls  # an injected client is the caller's


def test_mqtt_builds_and_closes_its_own_client(monkeypatch):
    """Without ``client`` the source connects, starts the loop, and stops it on close."""
    fake = SimpleNamespace(
        Client=FakeMQTTClient, CallbackAPIVersion=SimpleNamespace(VERSION2="v2")
    )
    monkeypatch.setattr(connectors, "require", lambda module, extra: fake)
    source = MQTTSource("t", host="broker", port=1884)
    assert source.client.args == ("v2",)
    assert source.client.calls[:2] == [("connect", "broker", 1884), ("loop_start",)]
    source.close()
    assert source.client.calls[-2:] == [("loop_stop",), ("disconnect",)]


def test_kafka_reads_batches_and_keeps_errors():
    """Each poll consumes a batch; error messages are kept aside, not decoded."""
    consumer = FakeConsumer()
    source = KafkaSource("cases", consumer=consumer, timeout=0.5)
    assert consumer.subscribed == ["cases"]
    eof = object()
    consumer.batches = [[FakeMessage(_record(2, 4)), FakeMessage(error=eof)]]
    assert [o.time for o in source.poll()] == [2.0]
    assert source.errors == [eof]
    assert consumer.consumed[0][1] == 0.5
    assert source.poll() == []
    source.close()
    assert consumer.closed


def test_kafka_builds_its_consumer_from_config(monkeypatch):
    """With ``config`` the source builds a consumer; exactly one of the two is needed."""
    fake = SimpleNamespace(Consumer=FakeConsumer)
    monkeypatch.setattr(connectors, "require", lambda module, extra: fake)
    source = KafkaSource("cases", config={"group.id": "twin"})
    assert source.consumer.config == {"group.id": "twin"}
    with pytest.raises(ValueError, match="exactly one"):
        KafkaSource("cases")


@pytest.mark.parametrize(
    ("module", "build"),
    [
        ("paho", lambda: MQTTSource("t")),
        ("confluent_kafka", lambda: KafkaSource("t", config={})),
    ],
)
def test_a_missing_client_library_names_the_extra(monkeypatch, module, build):
    """Without the library the error says which extra to install."""
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(ImportError, match="modelly-abm"):
        build()
