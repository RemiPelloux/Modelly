"""POST a JSON body and read a JSON reply with ``urllib`` alone: no provider SDK needed.

Error messages name the URL and the status, never the headers, so an API key cannot
leak into a log or a traceback.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from modelly.llm.errors import ProviderError

if TYPE_CHECKING:
    import urllib.error
    from email.message import Message

# Seconds to wait for a reply before the call counts as failed (and may be retried).
DEFAULT_TIMEOUT = 120.0
# How much of an error body an exception quotes.
BODY_EXCERPT = 300
# Statuses below this are a reply; redirects are left to urllib, which follows them.
FIRST_REDIRECT = 300
FIRST_ERROR = 400


def post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    """Send ``payload`` to ``url`` and return the decoded JSON reply.

    The call goes through this thread's kept connection to the host
    (``modelly.llm._connections``), or through ``urllib`` behind a proxy or in Pyodide.

    Raises:
        ProviderError: On an HTTP error status, a lost connection, a timeout or a
            reply that is not JSON. ``retryable`` says whether to try again.
    """
    from modelly.llm import _connections as connections  # noqa: PLC0415 - http.client loads on use

    data = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json", **headers}
    body = None
    if connections.reusable(url):
        body = _post_kept(url, data, headers, timeout)
    if body is None:
        body = _post_urllib(url, data, headers, timeout)
    try:
        parsed: dict[str, Any] = json.loads(body.decode("utf-8"))
        return parsed
    except ValueError:
        raise ProviderError(f"POST {url} returned a reply that is not JSON") from None


def _post_kept(
    url: str, data: bytes, headers: dict[str, str], timeout: float
) -> bytes | None:
    """The reply body through a kept connection; None for a redirect (urllib follows)."""
    import http.client  # noqa: PLC0415 - loaded by connections already

    from modelly.llm import _connections as connections  # noqa: PLC0415

    try:
        status, reply_headers, body = connections.post(url, data, headers, timeout)
    except (OSError, http.client.HTTPException) as error:
        raise ProviderError(f"POST {url} failed: {error}") from None
    if status < FIRST_REDIRECT:
        return body
    if status < FIRST_ERROR:
        return None
    detail = body.decode("utf-8", errors="replace")[:BODY_EXCERPT]
    raise _status_error(url, status, detail, reply_headers)


def _post_urllib(
    url: str, data: bytes, headers: dict[str, str], timeout: float
) -> bytes:
    """The reply body through ``urllib``, which also honours proxies and redirects."""
    import urllib.error  # noqa: PLC0415 - loaded on use, not at import
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            body: bytes = reply.read()
            return body
    except urllib.error.HTTPError as error:
        raise http_error(url, error) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        reason = getattr(error, "reason", error)
        raise ProviderError(f"POST {url} failed: {reason}") from None


def http_error(url: str, error: urllib.error.HTTPError) -> ProviderError:
    """A :class:`ProviderError` for an error status, with the server's retry hint."""
    try:
        detail = error.read().decode("utf-8", errors="replace")[:BODY_EXCERPT]
    except OSError:
        detail = ""
    finally:
        error.close()
    return _status_error(url, error.code, detail, error.headers)


def _status_error(
    url: str, status: int, detail: str, headers: Message
) -> ProviderError:
    """A :class:`ProviderError` for ``status``, quoting ``detail`` and the retry hint."""
    return ProviderError(
        f"POST {url} returned {status}: {detail}",
        status=status,
        retry_after=retry_after(headers.get("retry-after")),
    )


def retry_after(value: str | None) -> float | None:
    """The ``Retry-After`` header in seconds, when it is a number."""
    try:
        return None if value is None else max(0.0, float(value))
    except ValueError:
        return None
