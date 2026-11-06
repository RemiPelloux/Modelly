"""Kept HTTP connections, the memoised request key, batched cache reads and the client pool."""

import pickle
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from modelly.llm import (
    Client,
    FakeProvider,
    Message,
    OpenAICompatibleProvider,
    Request,
    ResponseCache,
    RetryPolicy,
)
from modelly.llm import _connections as connections
from modelly.llm import cache as cache_module

REPLY = b'{"choices": [{"message": {"content": "Hi"}}], "usage": {}}'
POLL = 0.01  # seconds between shutdown checks of the server loop
WAIT = 5.0  # seconds to wait for the server to close a connection


class KeepAlive(BaseHTTPRequestHandler):
    """An HTTP/1.1 handler that keeps the connection open and counts connections."""

    protocol_version = "HTTP/1.1"

    def setup(self):
        """Count the new connection."""
        super().setup()
        self.server.connections += 1

    def finish(self):
        """Count the closed connection."""
        super().finish()
        self.server.closed += 1

    def do_POST(self):
        """Answer, then close the connection if the test asks for it."""
        self.rfile.read(int(self.headers.get("content-length", 0)))
        self.send_response(200)
        self.send_header("content-length", str(len(REPLY)))
        self.end_headers()
        self.wfile.write(REPLY)
        self.wfile.flush()
        if self.server.hang_up:
            self.close_connection = True

    def log_message(self, *args):
        """Keep the test output quiet."""


@pytest.fixture
def keep_alive():
    """A running HTTP/1.1 server with a connection counter."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), KeepAlive)
    httpd.connections = 0
    httpd.closed = 0
    httpd.hang_up = False
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": POLL}, daemon=True
    )
    thread.start()
    yield httpd
    connections.close_all()
    httpd.shutdown()
    httpd.server_close()
    thread.join()


@pytest.fixture(autouse=True)
def keep_http(monkeypatch):
    """Keep plain-http connections too, so the local server can stand in for HTTPS."""
    monkeypatch.setattr(connections, "KEPT_SCHEMES", frozenset({"http", "https"}))


def client_for(httpd):
    """A one-thread client on the server, with no retries."""
    url = f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    provider = OpenAICompatibleProvider(base_url=url, name="local")
    return Client(
        provider, model="m", retry=RetryPolicy(max_retries=0), max_concurrency=1
    )


def test_calls_reuse_one_connection(keep_alive, monkeypatch):
    """Three calls from one thread open one connection."""
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    client = client_for(keep_alive)
    for prompt in ("a", "b", "c"):
        assert client.complete(prompt).text == "Hi"
    assert keep_alive.connections == 1


def test_connection_closed_by_the_server_is_replaced(keep_alive, monkeypatch):
    """After the server hangs up, the next call opens a new connection and succeeds."""
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    keep_alive.hang_up = True
    client = client_for(keep_alive)
    for prompt in ("a", "b"):
        assert client.complete(prompt).text == "Hi"
    assert keep_alive.connections == 2


def test_stale_connection_is_retried_once(keep_alive, monkeypatch):
    """A closed connection not noticed before reuse fails without a reply: sent again."""
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.setattr(connections, "dropped", lambda connection: False)
    keep_alive.hang_up = True
    client = client_for(keep_alive)
    assert client.complete("a").text == "Hi"
    deadline = time.monotonic() + WAIT
    while keep_alive.closed < 1 and time.monotonic() < deadline:
        time.sleep(POLL)
    assert client.complete("b").text == "Hi"
    assert keep_alive.connections == 2


def test_proxy_falls_back_to_urllib(monkeypatch):
    """Behind a proxy, calls go through urllib, which honours it."""
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:3128")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    assert not connections.reusable("http://example.org/v1")
    assert not connections.reusable("ftp://example.org/")


def test_plain_http_is_not_kept_by_default(monkeypatch):
    """Only https connections are kept unless told otherwise."""
    monkeypatch.undo()
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    assert frozenset({"https"}) == connections.KEPT_SCHEMES
    assert not connections.reusable("http://127.0.0.1:11434/v1")


def test_request_key_is_memoised_outside_the_fields():
    """The key is computed once; equality, repr and pickles ignore the memo."""
    request = Request("fake", "m", (Message("user", "Hi"),))
    fresh = Request("fake", "m", (Message("user", "Hi"),))
    key = request.key()
    assert request.key() is key
    assert request == fresh
    assert hash(request) == hash(fresh)
    assert repr(request) == repr(fresh)
    assert pickle.dumps(request) == pickle.dumps(fresh)
    assert pickle.loads(pickle.dumps(request)).key() == key  # noqa: S301


def test_get_many_reads_in_chunks(monkeypatch):
    """Lookups split into chunks below SQLite's variable limit, duplicates included."""
    monkeypatch.setattr(cache_module, "IN_CHUNK", 2)
    client = Client(FakeProvider())
    requests = [client.request(f"q{i}") for i in range(5)]
    client.complete_many(requests[:3])
    keys = [r.key() for r in requests] + [requests[0].key()]
    found = client.cache.get_many(keys)
    assert sorted(found) == sorted(r.key() for r in requests[:3])
    assert all(reply.cached for reply in found.values())


def test_batch_hits_are_counted_and_replies_cached_together():
    """A second batch is answered from the cache, in order."""
    client = Client(FakeProvider(), max_concurrency=3)
    requests = [client.request(f"q{i}") for i in range(6)]
    first = client.complete_many(requests)
    second = client.complete_many(requests)
    assert [r.text for r in first] == [r.text for r in second]
    assert all(r.cached for r in second)
    assert client.usage.cache_hits == len(requests)
    assert len(client.cache) == len(requests)


def test_client_pool_is_kept_and_left_out_of_pickles():
    """One pool serves every batch; a pickled client makes its own."""
    client = Client(FakeProvider(), max_concurrency=2)
    client.complete_many([client.request("a"), client.request("b")])
    pool = client.executor()
    client.complete_many([client.request("c"), client.request("d")])
    assert client.executor() is pool
    restored = pickle.loads(pickle.dumps(client))  # noqa: S301
    assert restored.executor() is not pool


def test_fake_failures_play_back_in_order():
    """The queued statuses fail the calls in order, then the provider answers."""
    fake = FakeProvider(lambda r: "ok", failures=[429, 503])
    client = Client(fake, retry=RetryPolicy(max_retries=2, sleeper=lambda s: None))
    assert client.complete("x").text == "ok"
    assert fake.calls == len(fake.requests) == 3
    assert not fake.failures


def test_batch_written_to_a_file_reopens(tmp_path):
    """A file cache written in one batch reopens with every row."""
    path = tmp_path / "c.sqlite"
    client = Client(FakeProvider(), cache=ResponseCache(path))
    client.complete_many([client.request(f"q{i}") for i in range(4)])
    client.cache.close()
    assert len(ResponseCache(path)) == 4
