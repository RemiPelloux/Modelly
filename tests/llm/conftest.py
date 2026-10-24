"""Fixtures for modelly.llm: a local HTTP server standing in for the providers."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ANTHROPIC_REPLY = {
    "content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": " there"}],
    "usage": {"input_tokens": 11, "output_tokens": 3},
}
OPENAI_REPLY = {
    "choices": [{"message": {"role": "assistant", "content": "Hi"}}],
    "usage": {"prompt_tokens": 7, "completion_tokens": 2},
}
OK = 200
POLL = 0.01  # seconds between shutdown checks of the server loop


class Handler(BaseHTTPRequestHandler):
    """Record each POST and answer with the next scripted reply, or a provider's default."""

    def do_POST(self):
        """Log the call, then reply."""
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.log.append(
            {"path": self.path, "headers": dict(self.headers), "body": body}
        )
        status, headers, payload = self.server.next_reply(self.path)
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        """Keep the test output quiet."""


class FakeServer(ThreadingHTTPServer):
    """A server on 127.0.0.1 with a request log and a queue of scripted replies."""

    def __init__(self):
        """Bind to a free port."""
        super().__init__(("127.0.0.1", 0), Handler)
        self.log = []
        self.script = []
        self.lock = threading.Lock()

    @property
    def url(self):
        """The base URL of the server."""
        return f"http://127.0.0.1:{self.server_address[1]}"

    def next_reply(self, path):
        """The next scripted ``(status, headers, body)``, else a provider's default."""
        with self.lock:
            if self.script:
                return self.script.pop(0)
        reply = ANTHROPIC_REPLY if path.endswith("/messages") else OPENAI_REPLY
        return OK, {"content-type": "application/json"}, reply


@pytest.fixture
def server():
    """A running local server, shut down after the test."""
    httpd = FakeServer()
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": POLL}, daemon=True
    )
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join()


@pytest.fixture
def delays():
    """A list to use as ``sleeper=delays.append``: records each wait, never sleeps."""
    return []
