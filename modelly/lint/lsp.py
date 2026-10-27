"""``modelly lint --lsp``: the linter as a language server, speaking LSP over stdio.

An editor starts ``modelly lint --lsp`` (or ``python -m modelly.lint --lsp``) and talks to
it on stdin and stdout. The server publishes the findings of every open Python file as
diagnostics when it is opened, changed or saved, honouring ``[tool.modelly.lint]`` of the
nearest pyproject.toml, and offers two code actions per finding: the safe fix of
``modelly lint --fix`` when the rule has one, and a ``# noqa`` comment for the line.
Only the standard library is used: the protocol subset is in ``modelly.lint.rpc``.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import modelly
from modelly.lint import Finding, lint_source
from modelly.lint.config import Config, load_config
from modelly.lint.edits import Edit, Source
from modelly.lint.fixers import FixCollector
from modelly.lint.lsp_items import QUICKFIX, action, diagnostic, hit_of, text_edit
from modelly.lint.rpc import error, notification, read_message, response, write_message
from modelly.lint.siblings import SiblingColumns

__all__ = ["Server", "serve"]

NAME = "modelly-lint"
SYNC_FULL = 1  # TextDocumentSyncKind.Full: every change sends the whole text
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603
EXIT_CLEAN = 0
EXIT_WITHOUT_SHUTDOWN = 1  # the spec's exit code when "exit" comes before "shutdown"
PUBLISH = "textDocument/publishDiagnostics"
NOQA = "# noqa"

Params = dict[str, Any]


def uri_path(uri: str) -> Path:
    """The file a ``file://`` URI names (any other scheme gives a relative, unmatched path)."""
    parsed = urlparse(uri)
    return (
        Path(url2pathname(unquote(parsed.path)))
        if parsed.scheme == "file"
        else Path(uri)
    )


def file_config(path: Path) -> Config:
    """The lint settings for ``path``; the defaults when its pyproject.toml is unusable."""
    try:
        return load_config(path.parent)
    except (OSError, ValueError):
        return Config()


def findings_of(uri: str, text: str) -> list[Finding]:
    """The findings the configuration keeps; none while the text does not parse."""
    path = uri_path(uri)
    config = file_config(path)
    root = config.root if config.root != Path() else path.parent
    try:
        found = lint_source(text, str(path), SiblingColumns([root]))
    except (SyntaxError, ValueError):
        return []
    return [finding for finding in found if config.keeps(finding)]


class Server:
    """The open documents and the handlers of the requests and notifications used."""

    def __init__(self, out: BinaryIO) -> None:
        """Write replies and notifications to ``out``; no document is open yet."""
        self.out = out
        self.documents: dict[str, str] = {}
        self.shut_down = False
        self.exited = False

    def send(self, message: Params) -> None:
        """Write one message to the client."""
        write_message(self.out, message)

    def publish(self, uri: str) -> None:
        """Send the diagnostics of ``uri``: none once it is closed."""
        text = self.documents.get(uri)
        found = findings_of(uri, text) if text is not None else []
        lines = text.splitlines() if text is not None else []
        items = [diagnostic(finding, lines) for finding in found]
        self.send(notification(PUBLISH, {"uri": uri, "diagnostics": items}))

    def dispatch(self, message: Params) -> None:
        """Run the handler of ``message``; reply when it is a request."""
        method, params = message.get("method"), message.get("params") or {}
        if "id" not in message:
            handler = NOTIFICATIONS.get(method)
            if handler is not None:
                handler(self, params)
            return
        request = REQUESTS.get(method)
        if request is None:
            self.send(
                error(message["id"], METHOD_NOT_FOUND, f"unknown method {method}")
            )
            return
        try:
            self.send(response(message["id"], request(self, params)))
        except (KeyError, TypeError, ValueError) as failure:
            self.send(error(message["id"], INTERNAL_ERROR, f"{method}: {failure}"))

    # Requests.

    def initialize(self, params: Params) -> Params:
        """Announce full-text sync, save notifications with text, and quick fixes."""
        sync = {"openClose": True, "change": SYNC_FULL, "save": {"includeText": True}}
        return {
            "capabilities": {
                "textDocumentSync": sync,
                "codeActionProvider": {"codeActionKinds": [QUICKFIX]},
            },
            "serverInfo": {"name": NAME, "version": modelly.__version__},
        }

    def shutdown(self, params: Params) -> None:
        """Agree to stop; ``exit`` follows."""
        self.shut_down = True

    def code_actions(self, params: Params) -> list[Params]:
        """The fix and the ``# noqa`` actions for the diagnostics the client sent."""
        uri = params["textDocument"]["uri"]
        text = self.documents.get(uri)
        if text is None:
            return []
        source = Source(text)
        fixes = self.fixes(source)
        actions = []
        for diag in params.get("context", {}).get("diagnostics", []):
            hit = hit_of(diag)
            if hit is None:
                continue
            if hit in fixes:
                title = f"Fix {hit[2]}"
                actions.append(
                    action(title, uri, diag, [text_edit(source, fixes[hit])])
                )
            actions.extend(self.noqa_action(source, uri, diag, hit))
        return actions

    @staticmethod
    def fixes(source: Source) -> dict[tuple[int, int, str], Edit]:
        """The safe fix of every fixable hit of ``source``, by position and code."""
        collector = FixCollector(source)
        try:
            collector.visit(ast.parse(source.text))
        except (SyntaxError, ValueError):
            return {}
        return dict(collector.fixes)

    @staticmethod
    def noqa_action(source: Source, uri: str, diag: Params, hit: tuple) -> list[Params]:
        """``# noqa: CODE`` at the end of the finding's line, unless it has a noqa already."""
        line = hit[0]
        if line > len(source.lines):
            return []
        text = source.line_text(line).rstrip("\r\n")
        if NOQA in text:
            return []
        at = source.starts[line - 1] + len(text)
        edit = text_edit(source, Edit(at, at, f"  {NOQA}: {hit[2]}"))
        return [action(f"Silence {hit[2]} on this line", uri, diag, [edit])]

    # Notifications.

    def opened(self, params: Params) -> None:
        """Track a newly opened document and lint it."""
        document = params["textDocument"]
        self.documents[document["uri"]] = document["text"]
        self.publish(document["uri"])

    def changed(self, params: Params) -> None:
        """Replace the text (full sync: the last change holds all of it) and lint it."""
        uri = params["textDocument"]["uri"]
        changes = params.get("contentChanges") or []
        if changes:
            self.documents[uri] = changes[-1]["text"]
        self.publish(uri)

    def saved(self, params: Params) -> None:
        """Lint the saved text."""
        uri = params["textDocument"]["uri"]
        if "text" in params:
            self.documents[uri] = params["text"]
        self.publish(uri)

    def closed(self, params: Params) -> None:
        """Forget a closed document and clear its diagnostics."""
        uri = params["textDocument"]["uri"]
        self.documents.pop(uri, None)
        self.publish(uri)

    def exit(self, params: Params) -> None:
        """Stop the message loop."""
        self.exited = True


REQUESTS: dict[str, Callable[[Server, Params], Any]] = {
    "initialize": Server.initialize,
    "shutdown": Server.shutdown,
    "textDocument/codeAction": Server.code_actions,
}
NOTIFICATIONS: dict[str, Callable[[Server, Params], None]] = {
    "initialized": lambda server, params: None,
    "exit": Server.exit,
    "textDocument/didOpen": Server.opened,
    "textDocument/didChange": Server.changed,
    "textDocument/didSave": Server.saved,
    "textDocument/didClose": Server.closed,
}


def serve(reader: BinaryIO, writer: BinaryIO) -> int:
    """Answer messages from ``reader`` on ``writer`` until ``exit``; return the exit status.

    Raises:
        ValueError: when the client sends a message that is not framed JSON.
    """
    server = Server(writer)
    while not server.exited:
        message = read_message(reader)
        if message is None:
            break
        server.dispatch(message)
    return EXIT_CLEAN if server.shut_down else EXIT_WITHOUT_SHUTDOWN
