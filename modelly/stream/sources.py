"""Where observations come from: a replayed table, a growing CSV file, an HTTP endpoint.

Every source has ``poll(until=None)``: the observations it has not handed out
yet, in time order, up to ``until`` when given (later ones wait for a later
poll). A source never hands out an observation twice, so a loop that polls
before each model step sees each data point exactly once. An observation that
arrives after a later one was handed out is dropped: a run cannot go back to
use it.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TIME = "time"
HTTP_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, order=True)
class Observation:
    """Values observed at one time; ``values`` maps a quantity to a number."""

    time: float
    values: Mapping[str, float] = field(compare=False)


def _observation(row: Mapping[str, Any], time: str) -> Observation:
    """An observation from a record with a ``time`` field; empty fields are dropped."""
    if time not in row:
        raise ValueError(f"record without a {time!r} field: {dict(row)}")
    values = {k: float(v) for k, v in row.items() if k != time and v not in ("", None)}
    return Observation(float(row[time]), {k: v for k, v in values.items() if v == v})


class _Buffered:
    """Keeps observations read but not yet handed out, in time order."""

    def __init__(self) -> None:
        """Start empty."""
        self._pending: list[Observation] = []
        self._last = float("-inf")

    def _take(self, until: float | None) -> list[Observation]:
        """Hand out pending observations up to ``until``."""
        self._pending.sort()
        cut = len(self._pending)
        if until is not None:
            cut = next((i for i, o in enumerate(self._pending) if o.time > until), cut)
        out, self._pending = self._pending[:cut], self._pending[cut:]
        if out:
            self._last = out[-1].time
        return out

    def _add(self, observations: Iterable[Observation]) -> None:
        """Queue observations later than the last one handed out."""
        self._pending.extend(o for o in observations if o.time > self._last)


class ReplaySource(_Buffered):
    """Observations from memory: a list of records, or a pandas DataFrame."""

    def __init__(self, records: Any, *, time: str = TIME) -> None:
        """Replay ``records`` (mappings with a ``time`` field, or a DataFrame)."""
        super().__init__()
        rows = records.to_dict("records") if hasattr(records, "to_dict") else records
        self._add(_observation(row, time) for row in rows)

    def poll(self, until: float | None = None) -> list[Observation]:
        """The observations not handed out yet, up to ``until``."""
        return self._take(until)


class CSVSource(_Buffered):
    """A CSV file that grows: each poll reads the rows appended since the last one."""

    def __init__(self, path: str | Path, *, time: str = TIME) -> None:
        """Follow ``path``; its first line is the header."""
        super().__init__()
        self.path = Path(path)
        self._time = time
        self._offset = 0
        self._header: list[str] | None = None

    def poll(self, until: float | None = None) -> list[Observation]:
        """Read complete new lines, then hand out what is due."""
        if self.path.exists():
            self._add(self._read_new())
        return self._take(until)

    def _read_new(self) -> list[Observation]:
        """Rows of complete lines after the last offset read."""
        with self.path.open("rb") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
        complete = chunk[: chunk.rfind(b"\n") + 1]
        self._offset += len(complete)
        lines = complete.decode("utf-8").splitlines()
        if self._header is None and lines:
            self._header = next(csv.reader([lines.pop(0)]))
        reader = csv.DictReader(io.StringIO("\n".join(lines)), fieldnames=self._header)
        return [_observation(row, self._time) for row in reader]


def _get(url: str) -> bytes:
    """The body of a GET request."""
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.read()


class HTTPSource(_Buffered):
    """An endpoint returning a JSON list of records; each poll fetches it again."""

    def __init__(
        self,
        url: str,
        *,
        time: str = TIME,
        fetch: Callable[[str], bytes] = _get,
        parse: Callable[[bytes], Iterable[Mapping[str, Any]]] = json.loads,
    ) -> None:
        """Poll ``url``; ``fetch`` and ``parse`` replace the HTTP call and the JSON decoding."""
        super().__init__()
        self.url = url
        self._time = time
        self._fetch = fetch
        self._parse = parse
        self._seen: set[float] = set()

    def poll(self, until: float | None = None) -> list[Observation]:
        """Fetch, keep records not seen before, then hand out what is due."""
        fresh = [
            _observation(r, self._time) for r in self._parse(self._fetch(self.url))
        ]
        new = [o for o in fresh if o.time not in self._seen]
        self._seen.update(o.time for o in new)
        self._add(new)
        return self._take(until)


def due(
    source: Any | Iterable[Observation], until: float | None = None
) -> list[Observation]:
    """The observations of ``source`` up to ``until``, in the order it gives them.

    ``source`` is a stream source (anything with ``poll(until)``) or an
    iterable of observations, such as a list.
    """
    poll = getattr(source, "poll", None)
    observations = poll(until) if poll is not None else source
    return [o for o in observations if until is None or o.time <= until]
