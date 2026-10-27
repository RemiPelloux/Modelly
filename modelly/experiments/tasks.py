"""One run of an experiment: the task a worker receives and the function it calls.

A :class:`RunTask` holds only plain values (the model as an import path, the
parameters, the seed's entropy and spawn key), so it pickles for processes,
Dask and Ray, and serialises to JSON for SLURM and PBS job arrays. Workers
started with ``spawn`` import the model by that path; nothing is inherited.

The run's generator comes from ``SeedSequence(entropy, spawn_key=(point,
replicate))``: the same numbers whatever executor, worker or order runs it.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
import traceback
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np

from modelly._optional import require
from modelly.experiments.store import KEYS, STEP, ResultsStore
from modelly.profile.loader import build_model

DONE, FAILED = "done", "failed"
REFERENCE = ":"  # "module:name" is an import reference, a bare name an attribute
INT64_MAX = np.iinfo(np.int64).max
SCALARS = (int, float, bool, str, type(None))
FILE_MODULE_PREFIX = "_modelly_experiment_"
FILE_KEY_LENGTH = 16  # hex digits of the path hash naming a model file's module

# Objects named by reference in this process: lets threads and the serial
# executor run classes and functions a fresh process could not import.
_OBJECTS: dict[str, Any] = {}


def reference(obj: Any) -> str:
    """``module:qualname`` of a class or function; a script's ``__main__`` becomes its path."""
    module, name = obj.__module__, obj.__qualname__
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if module == "__main__" and main_file:
        module = str(Path(main_file).resolve())
    ref = f"{module}{REFERENCE}{name}"
    _OBJECTS[ref] = obj
    return ref


def spawn_safe(ref: str) -> bool:
    """Whether a fresh process can import ``ref`` (not a notebook, lambda or closure)."""
    module, _, name = ref.rpartition(REFERENCE)
    return module != "__main__" and "<" not in name


def resolve(ref: str) -> Any:
    """The object ``ref`` names, imported on first use in this process."""
    if ref in _OBJECTS:
        return _OBJECTS[ref]
    module, _, name = ref.rpartition(REFERENCE)
    found = (
        _load_file(module)
        if module.endswith(".py")
        else importlib.import_module(module)
    )
    for part in name.split("."):
        found = getattr(found, part)
    _OBJECTS[ref] = found
    return found


def _load_file(source: str) -> Any:
    """Import the ``.py`` file ``source`` under a name unique to its path."""
    path = Path(source).resolve()
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:FILE_KEY_LENGTH]
    name = f"{FILE_MODULE_PREFIX}{digest}"
    if name in sys.modules:
        return sys.modules[name]
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None  # a .py path always has both
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_seed(entropy: int, point: int, replicate: int) -> int:
    """The integer seed recorded for a run (and the key resume works by)."""
    sequence = np.random.SeedSequence(entropy, spawn_key=(point, replicate))
    return int(sequence.generate_state(1, dtype=np.uint64)[0]) & int(INT64_MAX)


@dataclass(frozen=True)
class RunTask:
    """Everything one worker needs to run one (design point, replicate)."""

    model: str
    params: dict[str, Any]
    point: int
    replicate: int
    entropy: int
    steps: int
    outputs: dict[str, str]
    store: str
    retries: int = 0
    record_failures: bool = True

    @cached_property
    def seed(self) -> int:
        """This run's seed: a function of the experiment seed, point and replicate."""
        return run_seed(self.entropy, self.point, self.replicate)

    @property
    def run_id(self) -> str:
        """``<point>-<replicate>``."""
        return f"{self.point}-{self.replicate}"

    def seed_sequence(self) -> np.random.SeedSequence:
        """The SeedSequence child of this (point, replicate)."""
        return np.random.SeedSequence(
            self.entropy, spawn_key=(self.point, self.replicate)
        )

    def to_dict(self) -> dict[str, Any]:
        """The task as JSON-ready values."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunTask:
        """The task :meth:`to_dict` wrote."""
        return cls(**data)


@dataclass(frozen=True)
class RunOutcome:
    """What a worker reports back: the run, its status and the error if it failed."""

    run_id: str
    seed: int
    status: str
    attempts: int = 1
    error: str | None = None


def _reader(spec: str) -> Callable[[Any], Any]:
    """A function reading one output from a model: an attribute path or a reference."""
    if REFERENCE in spec:
        function: Callable[[Any], Any] = resolve(spec)
        return function

    def read(model: Any) -> Any:
        value = model
        for part in spec.split("."):
            value = getattr(value, part)
        return value() if callable(value) else value

    return read


def _scalar(name: str, value: Any) -> Any:
    """``value`` as a plain Python scalar, or a TypeError naming the output."""
    value = value.item() if isinstance(value, np.generic) else value
    if not isinstance(value, SCALARS):
        raise TypeError(f"output {name!r} must be a number, bool or str, got {value!r}")
    return value


def simulate(task: RunTask) -> Any:
    """Build the model, step it ``task.steps`` times and return the rows as a pyarrow Table.

    Row 0 is the state after construction; the run stops early when
    ``model.running`` becomes False.
    """
    pa = require("pyarrow", "experiments")
    model = build_model(resolve(task.model), dict(task.params), task.seed_sequence())
    readers = {name: _reader(spec) for name, spec in task.outputs.items()}
    columns: dict[str, list[Any]] = {STEP: [], **{name: [] for name in readers}}
    for step in range(task.steps + 1):
        if step and not model.running:
            break
        if step:
            model.step()
        columns[STEP].append(step)
        for name, read in readers.items():
            columns[name].append(_scalar(name, read(model)))
    rows = len(columns[STEP])
    keys = dict(zip(KEYS, (task.run_id, task.point, task.replicate, task.seed)))
    constant = {**keys, **task.params}
    return pa.table({**{k: [v] * rows for k, v in constant.items()}, **columns})


def run_task(task: RunTask) -> RunOutcome:
    """Run ``task`` (retrying ``task.retries`` times), store it, report the outcome.

    The function every executor calls; it never raises for a model error.
    """
    store = ResultsStore(task.store)
    error = ""
    attempts = task.retries + 1
    for attempt in range(1, attempts + 1):
        try:
            store.write_run(task.seed, simulate(task))
            return RunOutcome(task.run_id, task.seed, DONE, attempt)
        except Exception:  # a model error is the run's outcome, not the sweep's
            error = traceback.format_exc()
    if task.record_failures:
        record = {"run_id": task.run_id, "point": task.point}
        record |= {"replicate": task.replicate, "seed": task.seed}
        record |= {"params": task.params, "attempts": attempts, "error": error}
        store.record_failure(task.seed, record)
    return RunOutcome(task.run_id, task.seed, FAILED, attempts, error)
