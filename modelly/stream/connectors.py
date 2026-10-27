"""Message-broker sources: MQTT topics and Kafka topics (optional extras).

Both behave like the other stream sources: ``poll(until=None)`` hands out the
observations received since the last poll, in time order, each once. A
message's payload is a JSON record with a ``time`` field (or a list of them);
``parse`` replaces the decoding.

The client libraries are optional and imported only when a source builds its
own client::

    pip install "modelly-abm[mqtt]"    # paho-mqtt
    pip install "modelly-abm[kafka]"   # confluent-kafka

Pass ``client=`` (MQTT) or ``consumer=`` (Kafka) to use one you configured
yourself, with authentication, TLS and so on, or a stand-in in tests.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from modelly._optional import require
from modelly.stream.sources import TIME, Observation, _Buffered, _observation

MQTT_PORT = 1883
KAFKA_TIMEOUT_SECONDS = 1.0
KAFKA_BATCH = 500  # messages read per consume call

Parser = Callable[[bytes], Any]


def _records(payload: Any) -> Iterable[Mapping[str, Any]]:
    """A decoded payload as records: one mapping, or a list of them."""
    return [payload] if isinstance(payload, Mapping) else payload


def _mqtt_client(host: str, port: int) -> Any:
    """A connected paho-mqtt client running its network loop in a thread."""
    mqtt = require("paho.mqtt.client", "mqtt")
    version = getattr(mqtt, "CallbackAPIVersion", None)
    client = mqtt.Client(version.VERSION2) if version is not None else mqtt.Client()
    client.connect(host, port)
    client.loop_start()
    return client


class MQTTSource(_Buffered):
    """Observations published to an MQTT topic (paho-mqtt)."""

    def __init__(
        self,
        topic: str,
        *,
        host: str = "localhost",
        port: int = MQTT_PORT,
        client: Any = None,
        time: str = TIME,
        parse: Parser = json.loads,
    ) -> None:
        """Subscribe to ``topic`` on the broker at ``host:port``, or through ``client``.

        A ``client`` needs ``subscribe(topic)`` and an ``on_message``
        attribute, as a paho ``Client`` has; it is used as given (connected,
        its loop running). Messages arrive on the client's thread and wait in
        a queue for the next ``poll``.
        """
        super().__init__()
        self.topic = topic
        self._time = time
        self._parse = parse
        self._inbox: deque[bytes] = deque()
        self._owned = client is None
        self.client = _mqtt_client(host, port) if client is None else client
        self.client.on_message = self._on_message
        self.client.subscribe(topic)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        """Queue a message's payload (called by the client, on its thread)."""
        self._inbox.append(message.payload)

    def poll(self, until: float | None = None) -> list[Observation]:
        """Decode the messages received since the last poll, then hand out what is due."""
        while self._inbox:
            payload = self._parse(self._inbox.popleft())
            self._add(_observation(r, self._time) for r in _records(payload))
        return self._take(until)

    def close(self) -> None:
        """Stop and disconnect the client when this source created it."""
        if self._owned:
            self.client.loop_stop()
            self.client.disconnect()


def _kafka_consumer(config: Mapping[str, Any]) -> Any:
    """A confluent-kafka consumer built from ``config``."""
    kafka = require("confluent_kafka", "kafka")
    return kafka.Consumer(dict(config))


class KafkaSource(_Buffered):
    """Observations from a Kafka topic (confluent-kafka)."""

    def __init__(
        self,
        topic: str,
        *,
        config: Mapping[str, Any] | None = None,
        consumer: Any = None,
        time: str = TIME,
        parse: Parser = json.loads,
        timeout: float = KAFKA_TIMEOUT_SECONDS,
    ) -> None:
        """Consume ``topic`` with a consumer built from ``config``, or with ``consumer``.

        ``config`` is the confluent-kafka configuration, for example
        ``{"bootstrap.servers": "broker:9092", "group.id": "twin"}``. A
        ``consumer`` needs ``subscribe([topic])``, ``consume(num_messages,
        timeout)`` and ``close()``. Each poll waits at most ``timeout`` seconds.
        """
        if (config is None) == (consumer is None):
            raise ValueError("pass exactly one of config and consumer")
        super().__init__()
        self.topic = topic
        self._time = time
        self._parse = parse
        self._timeout = timeout
        self.consumer = _kafka_consumer(config) if consumer is None else consumer
        self.consumer.subscribe([topic])
        self.errors: list[Any] = []

    def poll(self, until: float | None = None) -> list[Observation]:
        """Read the messages waiting on the topic, then hand out what is due.

        Messages that carry an error (such as the end of a partition) are kept
        in ``errors`` instead of being decoded.
        """
        messages = self.consumer.consume(
            num_messages=KAFKA_BATCH, timeout=self._timeout
        )
        for message in messages:
            if message.error() is not None:
                self.errors.append(message.error())
                continue
            payload = self._parse(message.value())
            self._add(_observation(r, self._time) for r in _records(payload))
        return self._take(until)

    def close(self) -> None:
        """Leave the consumer group and close the consumer."""
        self.consumer.close()
