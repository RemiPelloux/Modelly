"""POST a JSON body and read a JSON reply with ``urllib`` alone: no provider SDK needed.

Error messages name the URL and the status, never the headers, so an API key cannot
leak into a log or a traceback.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from modelly.llm.errors import ProviderError

# Seconds to wait for a reply before the call counts as failed (and may be retried).
DEFAULT_TIMEOUT = 120.0
# How much of an error body an exception quotes.
BODY_EXCERPT = 300


def post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    """Send ``payload`` to ``url`` and return the decoded JSON reply.

    Raises:
        ProviderError: On an HTTP error status, a lost connection, a timeout or a
            reply that is not JSON. ``retryable`` says whether to try again.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"content-type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            body = reply.read()
    except urllib.error.HTTPError as error:
        raise http_error(url, error) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        reason = getattr(error, "reason", error)
        raise ProviderError(f"POST {url} failed: {reason}") from None
    try:
        parsed: dict[str, Any] = json.loads(body.decode("utf-8"))
        return parsed
    except ValueError:
        raise ProviderError(f"POST {url} returned a reply that is not JSON") from None


def http_error(url: str, error: urllib.error.HTTPError) -> ProviderError:
    """A :class:`ProviderError` for an error status, with the server's retry hint."""
    try:
        detail = error.read().decode("utf-8", errors="replace")[:BODY_EXCERPT]
    except OSError:
        detail = ""
    finally:
        error.close()
    return ProviderError(
        f"POST {url} returned {error.code}: {detail}",
        status=error.code,
        retry_after=retry_after(error.headers.get("retry-after")),
    )


def retry_after(value: str | None) -> float | None:
    """The ``Retry-After`` header in seconds, when it is a number."""
    try:
        return None if value is None else max(0.0, float(value))
    except ValueError:
        return None
