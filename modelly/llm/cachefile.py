"""The JSON-lines form of a response cache: one row per line, sorted by key.

``.jsonl`` is plain text a reviewer can read and diff; ``.jsonl.gz`` is the same text
compressed, with a zero timestamp so the same rows always give the same bytes.
"""

from __future__ import annotations

import gzip
import io
import json
from collections.abc import Iterable
from pathlib import Path
from typing import IO

COLUMNS = (
    "key",
    "provider",
    "model",
    "request",
    "text",
    "input_tokens",
    "output_tokens",
)
JSON_SUFFIXES = frozenset({".jsonl", ".json"})
GZIP_SUFFIX = ".gz"


def is_json_lines(path: Path) -> bool:
    """Whether ``path`` names a JSON-lines file, compressed or not."""
    suffixes = path.suffixes
    if suffixes[-1:] == [GZIP_SUFFIX]:
        suffixes = suffixes[:-1]
    return bool(suffixes) and suffixes[-1] in JSON_SUFFIXES


def open_text(path: Path, mode: str) -> IO[str]:
    """``path`` opened as UTF-8 text with LF line ends, through gzip for ``.gz``."""
    if path.suffix != GZIP_SUFFIX:
        return path.open(mode, encoding="utf-8", newline="\n")
    raw = gzip.GzipFile(
        filename="", fileobj=path.open(mode + "b"), mode=mode + "b", mtime=0
    )
    return _Closing(raw, encoding="utf-8", newline="\n")


class _Closing(io.TextIOWrapper):
    """A text wrapper over gzip that also closes the file under it."""

    def close(self) -> None:
        """Close the text layer, the gzip layer and the file."""
        inner = self.buffer.fileobj  # type: ignore[attr-defined]
        super().close()
        inner.close()


def write_json_lines(path: Path, rows: Iterable[tuple]) -> None:
    """One JSON object per row, keys sorted, the request as nested JSON."""
    with open_text(path, "w") as file:
        for row in rows:
            record = dict(zip(COLUMNS, row))
            record["request"] = json.loads(record["request"])
            file.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def read_json_lines(path: Path) -> list[tuple]:
    """The rows of a JSON-lines export, in :data:`COLUMNS` order."""
    rows = []
    with open_text(path, "r") as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            record["request"] = json.dumps(record["request"], sort_keys=True)
            rows.append(tuple(record[name] for name in COLUMNS))
    return rows
