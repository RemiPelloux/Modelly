"""JSON-RPC 2.0 over a byte stream with the Language Server Protocol's framing.

Each message is a header block (``Content-Length: N``, a blank line) and N bytes of
UTF-8 JSON. LSP counts columns in UTF-16 code units; the linter counts UTF-8 bytes
(``ast``) and string offsets (``modelly.lint.edits``), so the converters live here too.
"""

from __future__ import annotations

import bisect
import json
from typing import Any, BinaryIO

__all__ = [
    "error",
    "notification",
    "offset_position",
    "read_message",
    "response",
    "utf16_column",
    "write_message",
]

LENGTH_HEADER = "content-length"
ENCODING = "utf-8"
VERSION = "2.0"
UTF16 = "utf-16-le"
UTF16_UNIT = 2  # bytes per UTF-16 code unit

Message = dict[str, Any]


def read_message(stream: BinaryIO) -> Message | None:
    """The next message from ``stream``, or None when the stream has ended.

    Raises:
        ValueError: on a header block without ``Content-Length`` or a body that is not JSON.
    """
    length = None
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        name, _, value = line.decode("ascii").partition(":")
        if name.strip().lower() == LENGTH_HEADER:
            length = int(value)
    if length is None:
        raise ValueError("a message without a Content-Length header")
    message: Message = json.loads(stream.read(length).decode(ENCODING))
    return message


def write_message(stream: BinaryIO, message: Message) -> None:
    """Write ``message`` to ``stream`` with its header, and flush it."""
    body = json.dumps(message, separators=(",", ":")).encode(ENCODING)
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    stream.flush()


def response(request_id: Any, result: Any) -> Message:
    """The reply to request ``request_id``."""
    return {"jsonrpc": VERSION, "id": request_id, "result": result}


def error(request_id: Any, code: int, message: str) -> Message:
    """The error reply to request ``request_id``."""
    return {
        "jsonrpc": VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def notification(method: str, params: Any) -> Message:
    """A message that expects no reply."""
    return {"jsonrpc": VERSION, "method": method, "params": params}


def utf16_column(line: str, index: int) -> int:
    """The LSP column (UTF-16 code units) of string index ``index`` in ``line``."""
    return len(line[:index].encode(UTF16)) // UTF16_UNIT


def offset_position(starts: list[int], lines: list[str], offset: int) -> Message:
    """The LSP position of string ``offset``, given each line's start offset and text."""
    line = max(bisect.bisect_right(starts, offset) - 1, 0)
    text = lines[line] if line < len(lines) else ""
    return {"line": line, "character": utf16_column(text, offset - starts[line])}
