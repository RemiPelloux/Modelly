"""Model checkpoints: save a run to one file and resume it bit for bit.

A checkpoint is a short text header followed by a pickle of the model::

    MODELLY-CHECKPOINT
    {"format": 2, "modelly": "1.3.0", "python": "3.13", "compression": "gzip"}
    <pickle, compressed or not>

The header is read without unpickling anything, so a file from another format,
Modelly release or Python version is refused with a clear error before any of
its bytes run.

Security: the payload is a pickle, and unpickling runs code chosen by whoever
wrote the file. Only load checkpoints you created or otherwise trust.
"""

from __future__ import annotations

import gzip
import io
import itertools
import json
import os
import pickle
import sys
import types
import weakref
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

import modelly
from modelly.core._flatpickle import ShellPickler, dump_flat, load_flat
from modelly.core.exceptions import CheckpointError
from modelly.time.events.event import Event, Priority
from modelly.time.events.generator import EventGenerator

if TYPE_CHECKING:
    from modelly.core.model import Model

MAGIC = b"MODELLY-CHECKPOINT\n"
FORMAT_VERSION = 2  # 2: agents written flat (modelly.core._flatpickle)
PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL
# Version components that must match: Modelly major.minor, Python major.minor.
VERSION_PARTS = 2
GZIP = "gzip"
TEMP_SUFFIX = ".tmp"  # sibling file written first, then moved into place


def _release(version: str) -> str:
    """``major.minor`` of a dotted version string."""
    return ".".join(version.split(".")[:VERSION_PARTS])


def _python_version() -> str:
    """``major.minor`` of the running interpreter."""
    return ".".join(str(part) for part in sys.version_info[:VERSION_PARTS])


def _header(compression: str | None) -> dict[str, Any]:
    """The header written in front of the pickle."""
    return {
        "format": FORMAT_VERSION,
        "modelly": modelly.__version__,
        "python": _python_version(),
        "compression": compression,
    }


class _Gone:
    """A throwaway referent: a weak reference to one is dead at once."""


def _rebuild_ref(referent: Any) -> weakref.ref:
    """A weak reference to ``referent``, or a dead one when it was dead."""
    return weakref.ref(_Gone() if referent is None else referent)


def _rebuild_weak_method(method: Any) -> weakref.ref:
    """A ``WeakMethod`` for ``method``, or a dead reference when it was dead."""
    return _rebuild_ref(None) if method is None else weakref.WeakMethod(method)


def _importable(function: types.FunctionType) -> bool:
    """Whether pickle can find ``function`` again by module and qualified name."""
    found: Any = sys.modules.get(function.__module__)
    for part in function.__qualname__.split("."):
        found = getattr(found, part, None)
    return found is function


def _unsaveable(callback: Any) -> types.FunctionType | None:
    """The lambda or nested function inside ``callback``, if there is one."""
    while isinstance(callback, partial):
        callback = callback.func
    if isinstance(callback, types.FunctionType) and not _importable(callback):
        return callback
    return None


def _describe(function: types.FunctionType) -> str:
    """``module.qualname`` of a function, for error messages."""
    return f"{function.__module__}.{function.__qualname__}"


def _hint() -> str:
    """How to make a callback saveable."""
    return (
        "Lambdas and nested functions cannot be pickled; use a module-level "
        "function, a method of the model or an agent, or a partial of one."
    )


def _check_event(event: Event | EventGenerator) -> None:
    """Refuse an event or generator whose callback cannot be pickled."""
    ref = event.fn if isinstance(event, Event) else event.function
    function = _unsaveable(ref() if ref is not None else None)
    if function is None:
        return
    if isinstance(event, Event):
        what = f"event {event.unique_id} at time {event.time}"
    else:
        what = f"recurring event {event.schedule}"
    raise CheckpointError(
        f"Cannot checkpoint {what}: its callback {_describe(function)} is not "
        f"importable. {_hint()}"
    )


class _Pickler(ShellPickler):
    """Pickle with weak references kept weak and unpicklable callbacks named."""

    def reducer_override(self, obj: Any) -> Any:
        """Reduce weak references; refuse lambdas with a clear error."""
        shell = self.shell(obj)
        if shell is not NotImplemented:
            return shell
        kind = type(obj)
        if kind is weakref.WeakMethod:
            return _rebuild_weak_method, (obj(),)
        if kind is weakref.ReferenceType and obj.__callback__ is None:
            return _rebuild_ref, (obj(),)
        if kind is types.FunctionType and not _importable(obj):
            raise CheckpointError(f"Cannot checkpoint {_describe(obj)}. {_hint()}")
        if kind is Event or kind is EventGenerator:
            _check_event(obj)
        return NotImplemented


def _next_event_id() -> int:
    """The id the next Event will get, leaving the counter where it was."""
    upcoming = next(Event._ids)
    Event._ids = itertools.count(upcoming)
    return upcoming


def _dump_payload(model: Model) -> bytes:
    """Pickle the model and the event-id counter its ordering depends on."""
    buffer = io.BytesIO()
    payload = {"model": model, "next_event_id": _next_event_id()}
    dump_flat(_Pickler(buffer, PICKLE_PROTOCOL), model, payload)
    return buffer.getvalue()


def checkpoint_bytes(model: Model, *, compress: bool = False) -> bytes:
    """``model`` as the bytes of a checkpoint file: header, then the pickle."""
    payload = _dump_payload(model)
    compression = GZIP if compress else None
    if compress:
        payload = gzip.compress(payload)
    header = json.dumps(_header(compression)).encode() + b"\n"
    return MAGIC + header + payload


def save_model(model: Model, path: str | Path, *, compress: bool = False) -> None:
    """Write ``model`` to ``path`` as a checkpoint (see :meth:`Model.save`).

    The bytes go to a sibling temporary file first and ``os.replace`` moves it into
    place (atomic on every platform), so a reader never sees half a checkpoint.
    """
    target = Path(path)
    temporary = target.with_name(f".{target.name}{TEMP_SUFFIX}")
    temporary.write_bytes(checkpoint_bytes(model, compress=compress))
    os.replace(temporary, target)


def _read_header(file: BinaryIO, path: str | Path) -> dict[str, Any]:
    """Read and parse the header, refusing files that are not checkpoints."""
    if file.readline() != MAGIC:
        raise CheckpointError(f"{path} is not a Modelly checkpoint.")
    try:
        header = json.loads(file.readline())
    except ValueError as exc:
        raise CheckpointError(f"{path} has a damaged checkpoint header.") from exc
    if not isinstance(header, dict):
        raise CheckpointError(f"{path} has a damaged checkpoint header.")
    return header


def _check_compatible(header: dict[str, Any], path: str | Path) -> None:
    """Refuse a checkpoint written by another format, Modelly or Python release."""
    expected = _header(header.get("compression"))
    expected["modelly"] = _release(modelly.__version__)
    found = {**header, "modelly": _release(str(header.get("modelly", "")))}
    for key in ("format", "modelly", "python"):
        if found.get(key) != expected[key]:
            raise CheckpointError(
                f"{path} was written with {key} {header.get(key)!r}; this "
                f"process needs {expected[key]!r}. Load it with the matching "
                "release, or rerun the model."
            )


def _restore_event_ids(next_event_id: int) -> None:
    """Keep new events ordered after the restored ones, as in the original run."""
    Event._ids = itertools.count(max(next_event_id, _next_event_id()))


def load_model(path: str | Path) -> Model:
    """Read a checkpoint written by :func:`save_model` (see :meth:`Model.load`)."""
    with Path(path).open("rb") as file:
        return _load(file, path)


def model_from_bytes(data: bytes, source: str = "checkpoint") -> Model:
    """The model held by checkpoint bytes from :func:`checkpoint_bytes`."""
    return _load(io.BytesIO(data), source)


def _load(file: BinaryIO, path: str | Path) -> Model:
    """Check the header of an open checkpoint, then unpickle the model."""
    header = _read_header(file, path)
    _check_compatible(header, path)
    payload = file.read()
    if header.get("compression") == GZIP:
        payload = gzip.decompress(payload)
    state = load_flat(io.BytesIO(payload))
    _restore_event_ids(state["next_event_id"])
    return state["model"]


class CheckpointWriter:
    """Save the model every ``interval`` time units (see :meth:`Model.checkpoint_every`).

    Each save is a one-off LOW priority event that schedules the next one
    before writing, so the checkpoint itself holds the following save and a
    resumed run keeps checkpointing.
    """

    def __init__(
        self, model: Model, interval: float, path_pattern: str, compress: bool
    ) -> None:
        """Schedule the first save ``interval`` time units from now."""
        if interval <= 0:
            raise ValueError(f"Checkpoint interval must be > 0, got {interval}")
        self.model = model
        self.interval = interval
        self.path_pattern = path_pattern
        self.compress = compress
        # The event holds this writer weakly; the model keeps it alive.
        vars(model).setdefault("_checkpoint_writers", set()).add(self)
        self._event = model.schedule_event(
            self.write, after=interval, priority=Priority.LOW
        )

    def write(self) -> None:
        """Schedule the next save, then save to ``path_pattern.format(time=...)``."""
        self._event = self.model.schedule_event(
            self.write, after=self.interval, priority=Priority.LOW
        )
        path = self.path_pattern.format(time=self.model.time)
        save_model(self.model, path, compress=self.compress)

    def stop(self) -> None:
        """Cancel the next save."""
        self._event.cancel()
        self.model._checkpoint_writers.discard(self)
