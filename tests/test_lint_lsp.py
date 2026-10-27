"""Tests for ``modelly lint --lsp``: the language server driven over pipes, end to end."""

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from modelly.lint.lsp import Server, serve, uri_path
from modelly.lint.rpc import read_message, utf16_column, write_message

REPO = Path(__file__).resolve().parents[1]
TIMEOUT = 60  # seconds for the server process to answer everything and exit
BAD = "import random\nfrom modelly import Agent\nclass A(Agent):\n    def step(self):\n        x = random.random()\n"
GOOD = "from modelly import Agent\nclass A(Agent):\n    def step(self):\n        x = self.random.random()\n"


def frame(messages: list[dict]) -> bytes:
    """``messages`` framed as an LSP client writes them."""
    stream = io.BytesIO()
    for message in messages:
        write_message(stream, message)
    return stream.getvalue()


def unframe(data: bytes) -> list[dict]:
    """Every message in the server's output, in order."""
    stream, messages = io.BytesIO(data), []
    while (message := read_message(stream)) is not None:
        messages.append(message)
    return messages


def request(number: int, method: str, params: dict | None = None) -> dict:
    """A JSON-RPC request."""
    return {"jsonrpc": "2.0", "id": number, "method": method, "params": params or {}}


def notify(method: str, params: dict | None = None) -> dict:
    """A JSON-RPC notification."""
    return {"jsonrpc": "2.0", "method": method, "params": params or {}}


def opened(uri: str, text: str) -> dict:
    """A didOpen notification for a Python file."""
    document = {"uri": uri, "languageId": "python", "version": 1, "text": text}
    return notify("textDocument/didOpen", {"textDocument": document})


def run_server(messages: list[dict], cwd: Path) -> tuple[int, list[dict]]:
    """Start ``python -m modelly lint --lsp``, send ``messages``, return its status and output."""
    process = subprocess.run(
        [sys.executable, "-m", "modelly", "lint", "--lsp"],
        input=frame(messages),
        capture_output=True,
        cwd=cwd,
        timeout=TIMEOUT,
        check=False,
        env=os.environ | {"PYTHONPATH": str(REPO)},
    )
    return process.returncode, unframe(process.stdout)


def published(output: list[dict]) -> list[list[dict]]:
    """The diagnostics of every publishDiagnostics notification, in order."""
    return [
        m["params"]["diagnostics"]
        for m in output
        if m.get("method") == "textDocument/publishDiagnostics"
    ]


def test_open_change_save_close_and_quick_fix(tmp_path):
    """Diagnostics follow the text; the fix and noqa actions edit the finding's line."""
    uri = (tmp_path / "model.py").as_uri()
    finding = {
        "range": {
            "start": {"line": 4, "character": 12},
            "end": {"line": 4, "character": 27},
        },
        "code": "MDL001",
        "source": "modelly",
        "data": {"line": 5, "column": 13},
    }
    actions = {"textDocument": {"uri": uri}, "range": finding["range"]}
    actions["context"] = {"diagnostics": [finding]}
    messages = [
        request(
            1, "initialize", {"processId": None, "rootUri": None, "capabilities": {}}
        ),
        notify("initialized"),
        opened(uri, BAD),
        request(2, "textDocument/codeAction", actions),
        notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": 2},
                "contentChanges": [{"text": GOOD}],
            },
        ),
        notify("textDocument/didSave", {"textDocument": {"uri": uri}, "text": BAD}),
        notify("textDocument/didClose", {"textDocument": {"uri": uri}}),
        request(3, "no/such/method"),
        request(4, "shutdown"),
        notify("exit"),
    ]
    status, output = run_server(messages, tmp_path)
    assert status == 0
    replies = {m["id"]: m for m in output if "id" in m}
    capabilities = replies[1]["result"]["capabilities"]
    assert capabilities["textDocumentSync"]["change"] == 1
    assert capabilities["codeActionProvider"]["codeActionKinds"] == ["quickfix"]
    on_open, on_change, on_save, on_close = published(output)
    assert [d["code"] for d in on_open] == ["MDL001"]
    assert on_open[0]["range"]["start"] == {"line": 4, "character": 12}
    assert on_open[0]["severity"] == 1 and on_open[0]["source"] == "modelly"
    assert on_change == [] and [d["code"] for d in on_save] == ["MDL001"]
    assert on_close == []
    fix, noqa = replies[2]["result"]
    (edit,) = fix["edit"]["changes"][uri]
    assert fix["kind"] == "quickfix" and edit["newText"] == "self.random.random"
    assert edit["range"]["start"] == {"line": 4, "character": 12}
    assert noqa["edit"]["changes"][uri][0]["newText"] == "  # noqa: MDL001"
    assert replies[3]["error"]["code"] == -32601
    assert replies[4]["result"] is None


def test_configuration_and_syntax_errors(tmp_path):
    """[tool.modelly.lint] drops ignored rules; text that does not parse has no findings."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.modelly.lint]\nignore = ["MDL001"]\n', encoding="utf-8"
    )
    uri = (tmp_path / "model.py").as_uri()
    messages = [
        request(1, "initialize"),
        opened(uri, BAD),
        opened((tmp_path / "broken.py").as_uri(), "def (:\n"),
        request(2, "shutdown"),
        notify("exit"),
    ]
    status, output = run_server(messages, tmp_path)
    assert status == 0
    assert published(output) == [[], []]


def test_exit_without_shutdown_and_end_of_stream():
    """``exit`` before ``shutdown`` exits 1, as the protocol asks; so does a closed stdin."""
    out = io.BytesIO()
    assert serve(io.BytesIO(frame([notify("exit")])), out) == 1
    assert serve(io.BytesIO(b""), out) == 1
    with pytest.raises(ValueError, match="Content-Length"):
        serve(io.BytesIO(b"X-Other: 1\r\n\r\n{}"), out)


def test_code_action_edge_cases():
    """Unknown documents, foreign diagnostics and lines with a noqa get no action."""
    server = Server(io.BytesIO())
    assert server.code_actions({"textDocument": {"uri": "file:///x.py"}}) == []
    server.documents["file:///x.py"] = (
        "import random\nx = random.random()  # noqa: MDL101\n"
    )
    foreign = {"code": "E501", "source": "ruff", "data": {"line": 2, "column": 5}}
    ours = {"code": "MDL001", "source": "modelly", "data": {"line": 2, "column": 5}}
    broken = {"code": "MDL001", "source": "modelly", "data": {"line": "2"}}
    params = {"textDocument": {"uri": "file:///x.py"}}
    params["context"] = {"diagnostics": [foreign, ours, broken]}
    assert server.code_actions(params) == []  # outside a method: no fix; noqa present


def test_positions_count_utf16_units(tmp_path):
    """A character outside the BMP is two UTF-16 units, as LSP counts columns."""
    assert utf16_column("é𝄞x", 2) == 3  # é is one unit, the clef two
    assert utf16_column("é𝄞x", 3) == 4
    spaced = tmp_path / "a b.py"
    assert "%20" in spaced.as_uri() and uri_path(spaced.as_uri()) == spaced
