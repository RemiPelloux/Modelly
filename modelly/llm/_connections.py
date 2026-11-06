"""Keep-alive HTTP connections, one per thread and host, for repeated POSTs to one API.

``urllib`` opens a new connection, and a new TLS session, for every call. A run that
sends thousands of calls to one provider reuses one connection per thread instead.
A connection the server has closed while idle is noticed before reuse and replaced, so
a request is never written to a dead socket. The caller falls back to ``urllib`` when
:func:`reusable` says no: behind a proxy, in Pyodide, or for a scheme not in
:data:`KEPT_SCHEMES`. Plain ``http`` (a local server such as Ollama) is not kept: the
handshake it would save is cheap, and a server that writes a reply's headers and body
in two packets stalls a kept connection by the delayed-ACK timeout (~40 ms) per call.
"""

from __future__ import annotations

import http.client
import select
import sys
import threading
from email.message import Message
from urllib.parse import SplitResult, urlsplit

# The User-Agent urllib sends, so a server sees the same client either way.
USER_AGENT = f"Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"
SCHEMES = {"http": http.client.HTTPConnection, "https": http.client.HTTPSConnection}
# The schemes whose connections are kept (see the module notes for why not http).
KEPT_SCHEMES = frozenset({"https"})
# How a kept connection the server already closed fails: no reply byte came back.
STALE = (http.client.RemoteDisconnected, BrokenPipeError, ConnectionResetError)


class Connections(dict[tuple[str, str], http.client.HTTPConnection]):
    """One thread's open connections by ``(scheme, host)``; closed when the thread ends."""

    def __del__(self) -> None:
        """Close every connection, so none is left to the garbage collector."""
        for connection in self.values():
            connection.close()


_local = threading.local()


def reusable(url: str) -> bool:
    """Whether ``url`` can go through a kept connection (else urllib sends it)."""
    if sys.platform == "emscripten":
        return False
    parts = urlsplit(url)
    if parts.scheme not in KEPT_SCHEMES or not parts.hostname:
        return False
    import urllib.request  # noqa: PLC0415 - only when a call is made

    proxies = urllib.request.getproxies()
    return parts.scheme not in proxies or bool(
        urllib.request.proxy_bypass(parts.hostname)
    )


def post(
    url: str, data: bytes, headers: dict[str, str], timeout: float
) -> tuple[int, Message, bytes]:
    """POST ``data`` to ``url`` on this thread's connection: status, headers and body.

    A kept connection the server closed just as the request went out (it ends before
    any reply byte) is replaced and the request sent once more on a new connection:
    the server closed it idle, so it did not read the request. Any other lost
    connection is raised, and the client's ``RetryPolicy`` decides, as with urllib.

    Raises:
        OSError, http.client.HTTPException: The connection failed; it is discarded.
    """
    parts = urlsplit(url)
    connection = connection_for(parts, timeout)
    reused = connection.sock is not None
    try:
        return exchange(connection, parts, data, headers)
    except STALE:
        if not reused:
            raise
    return exchange(connection_for(parts, timeout), parts, data, headers)


def exchange(
    connection: http.client.HTTPConnection,
    parts: SplitResult,
    data: bytes,
    headers: dict[str, str],
) -> tuple[int, Message, bytes]:
    """One request and its reply on ``connection``; discarded when it fails or closes."""
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    try:
        connection.request(
            "POST", target, body=data, headers={"User-Agent": USER_AGENT, **headers}
        )
        reply = connection.getresponse()
        body = reply.read()
    except (OSError, http.client.HTTPException):
        discard(parts)
        raise
    if reply.will_close:
        discard(parts)
    return reply.status, reply.headers, body


def connection_for(parts: SplitResult, timeout: float) -> http.client.HTTPConnection:
    """This thread's open connection to the host of ``parts``, or a new one."""
    pool: Connections | None = _local.__dict__.get("pool")
    if pool is None:
        pool = _local.pool = Connections()
    key = (parts.scheme, parts.netloc)
    connection = pool.get(key)
    if connection is not None and dropped(connection):
        discard(parts)
        connection = None
    if connection is None:
        connection = SCHEMES[parts.scheme](parts.netloc, timeout=timeout)
        pool[key] = connection
    connection.timeout = timeout
    if connection.sock is not None:
        connection.sock.settimeout(timeout)
    return connection


def dropped(connection: http.client.HTTPConnection) -> bool:
    """Whether an idle connection was closed by the server (its socket reads as ready)."""
    if connection.sock is None:
        return False
    try:
        ready, _, _ = select.select([connection.sock], [], [], 0)
    except (OSError, ValueError):
        return True
    return bool(ready)


def discard(parts: SplitResult) -> None:
    """Close and forget this thread's connection to the host of ``parts``."""
    pool: Connections | None = _local.__dict__.get("pool")
    if pool is not None:
        connection = pool.pop((parts.scheme, parts.netloc), None)
        if connection is not None:
            connection.close()


def close_all() -> None:
    """Close every connection this thread keeps."""
    pool: Connections | None = _local.__dict__.pop("pool", None)
    if pool is not None:
        for connection in pool.values():
            connection.close()
        pool.clear()
