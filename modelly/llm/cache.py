"""The response cache: every reply stored under the key of the call that produced it.

The store is SQLite from the standard library, in memory or in one file, in the
rollback-journal mode (no WAL side files) with one transaction per write, so a crash
never leaves half a row. A cache travels as a SQLite file or as JSON lines, sorted by
key so the same responses always give the same file. It is pickled with the model, so
``Model.save`` keeps it in the checkpoint.

Modes:
    ``"read-write"``: a hit is returned without calling the provider; a miss calls it
    and stores the reply. ``"read-only"``: replay; a miss raises :class:`CacheMiss`.
    ``"off"``: every call goes to the provider and nothing is stored.

Example:
    >>> cache = ResponseCache()          # in memory
    >>> len(cache)
    0
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import weakref
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from modelly.llm.cachefile import (
    COLUMNS,
    is_json_lines,
    read_json_lines,
    write_json_lines,
)
from modelly.llm.request import Request, Response

READ_WRITE = "read-write"
READ_ONLY = "read-only"
OFF = "off"
MODES = (READ_WRITE, READ_ONLY, OFF)
MEMORY = ":memory:"
# An export is written to this name first, then renamed: the suffixes still say the format.
TEMPORARY_PREFIX = "tmp-"
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, provider TEXT, "
    "model TEXT, request TEXT, text TEXT, input_tokens INTEGER, output_tokens INTEGER)"
)
# Built from the constant column names above, never from user input.
INSERT = f"INSERT OR REPLACE INTO responses VALUES ({', '.join('?' * len(COLUMNS))})"  # noqa: S608
SELECT_ALL = f"SELECT {', '.join(COLUMNS)} FROM responses ORDER BY key"  # noqa: S608


class ResponseCache:
    """Replies by cache key, in memory (``path=None``) or in a SQLite file.

    Args:
        path: The SQLite file; created when missing. None keeps the cache in memory.
        mode: ``"read-write"``, ``"read-only"`` or ``"off"``.
    """

    def __init__(self, path: str | Path | None = None, mode: str = READ_WRITE) -> None:
        """Open (or create) the store."""
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        self.mode = mode
        self.path = None if path is None else Path(path)
        self._lock = threading.Lock()
        self._conn = connect(self.path)
        # Close the connection when the cache is collected, without a ResourceWarning.
        self._closer = weakref.finalize(self, self._conn.close)

    @classmethod
    def from_file(cls, path: str | Path, mode: str = READ_ONLY) -> ResponseCache:
        """An in-memory cache filled from an exported file (JSON lines or SQLite).

        The file itself is never written, so a cache shipped with a study bundle
        or a package stays as it was.
        """
        cache = cls(mode=mode)
        cache.merge(path)
        return cache

    @property
    def reads(self) -> bool:
        """Whether lookups are made (every mode but ``"off"``)."""
        return self.mode != OFF

    @property
    def writes(self) -> bool:
        """Whether new replies are stored (``"read-write"`` only)."""
        return self.mode == READ_WRITE

    def get(self, key: str) -> Response | None:
        """The stored reply for ``key``, marked ``cached``, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT text, input_tokens, output_tokens FROM responses WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return Response(row[0], row[1], row[2], cached=True, key=key)

    def put(self, request: Request, response: Response) -> None:
        """Store ``response`` under the key of ``request``, in one transaction."""
        row = (
            request.key(),
            request.provider,
            request.model,
            json.dumps(request.identity(), sort_keys=True),
            response.text,
            response.input_tokens,
            response.output_tokens,
        )
        self.insert([row])

    def insert(self, rows: list[tuple[Any, ...]]) -> None:
        """Write ``rows`` (in :data:`COLUMNS` order) atomically."""
        with self._lock, self._conn:
            self._conn.executemany(INSERT, rows)

    def rows(self) -> Iterator[tuple[Any, ...]]:
        """Every stored row, sorted by key."""
        with self._lock:
            found = self._conn.execute(SELECT_ALL).fetchall()
        yield from found

    def __len__(self) -> int:
        """The number of stored replies."""
        with self._lock:
            count: int = self._conn.execute(
                "SELECT COUNT(*) FROM responses"
            ).fetchone()[0]
            return count

    def __contains__(self, key: object) -> bool:
        """Whether a reply is stored under ``key``."""
        return isinstance(key, str) and self.get(key) is not None

    def export(self, path: str | Path) -> Path:
        """Write the cache to ``path``: JSON lines for ``.jsonl`` (``.jsonl.gz``), else SQLite.

        The file is written next to its target and renamed over it, so a reader
        never sees half a file.
        """
        target = Path(path)
        temporary = target.with_name(TEMPORARY_PREFIX + target.name)
        temporary.unlink(missing_ok=True)
        if is_json_lines(target):
            write_json_lines(temporary, self.rows())
        else:
            with self._lock:
                copy = sqlite3.connect(temporary)
                self._conn.backup(copy)
                copy.close()
        os.replace(temporary, target)
        return target

    def merge(self, path: str | Path) -> int:
        """Add every row of an exported file; return how many rows it held."""
        source = Path(path)
        if is_json_lines(source):
            rows = read_json_lines(source)
        else:
            other = sqlite3.connect(source)
            try:
                rows = other.execute(SELECT_ALL).fetchall()
            finally:
                other.close()
        self.insert(rows)
        return len(rows)

    def close(self) -> None:
        """Close the connection."""
        self._closer()

    def __getstate__(self) -> dict[str, Any]:
        """The path, the mode and every row: a checkpoint carries the whole cache."""
        path = None if self.path is None else str(self.path)
        return {"path": path, "mode": self.mode, "rows": list(self.rows())}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Reopen the file when its folder exists, else memory, and restore the rows."""
        path = state["path"]
        if path is not None and not Path(path).parent.is_dir():
            path = None
        type(self).__init__(self, path, state["mode"])
        self.insert(state["rows"])


def connect(path: Path | None) -> sqlite3.Connection:
    """A connection with the table, the rollback journal and full syncs."""
    conn = sqlite3.connect(
        MEMORY if path is None else str(path), check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=FULL")
    with conn:
        conn.execute(SCHEMA)
    return conn
