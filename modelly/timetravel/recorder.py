"""Record a run as a ring of checkpoints and rewind it to any step.

A :class:`Recorder` checkpoints the model when recording starts and then every
``every`` time units, holding the checkpoints in a ring
(:mod:`modelly.timetravel.ring`). ``at(step)`` restores the nearest checkpoint
at or before ``step`` and replays forward to it. Checkpoints and replay are
the 1.2 checkpoints (:meth:`modelly.Model.save`), so the model returned is the
one a straight run reaches at that step, bit for bit.
"""

from __future__ import annotations

import math
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.core.checkpoint import checkpoint_bytes, model_from_bytes
from modelly.timetravel.ring import DiskRing, MemoryRing

if TYPE_CHECKING:
    from modelly.core.model import Model

DEFAULT_EVERY = 10
MEBIBYTE = 2**20
DEFAULT_BUDGET = 256 * MEBIBYTE
# The attribute the recorder hooks on the model instance.
HOOK = "_advance_time"


def _plain_advance(model: Model[Any, Any]) -> types.MethodType:
    """The model's own ``_advance_time``, for a model pickled while recorded."""
    return types.MethodType(type(model)._advance_time, model)


class _Hook:
    """Advances time for the recorded model, stopping at each checkpoint."""

    def __init__(self, recorder: Recorder) -> None:
        """Advance on behalf of ``recorder``."""
        self.recorder = recorder

    def __call__(self, until: float) -> None:
        """Advance the model to ``until``, checkpointing on the way."""
        self.recorder._advance(until)

    def __reduce__(self) -> tuple[Any, ...]:
        """Pickle (``model.save`` while recording) as the plain method."""
        return _plain_advance, (self.recorder.model,)


def thaw(model: Model[Any, Any]) -> Model[Any, Any]:
    """Let ``model.scenario`` be changed, as on a model returned by ``at``."""
    object.__setattr__(model.scenario, "_frozen", False)
    return model


def reseed_model(model: Model[Any, Any], seed: np.random.SeedSequence) -> None:
    """Reseed both generators of ``model`` in place from ``seed``.

    ``model.rng`` gets a bit generator of its own class seeded with ``seed``
    and ``model.random`` the stdlib seed ``Model`` derives from a seed
    sequence, so spaces and columns holding the generators follow.
    """
    bit_generator = model.rng.bit_generator
    bit_generator.state = type(bit_generator)(seed).state
    model.random.seed(int(seed.generate_state(1, dtype=np.uint32)[0]))


class Recorder:
    """Checkpoint a model as it runs, to rewind, replay and branch it.

    Use it as a context manager, or call ``start()`` and ``stop()``::

        with Recorder(model, every=10) as rec:
            model.run_for(1000)
        past = rec.at(312)

    Args:
        model: The model to record.
        every: Time units between checkpoints; one is also taken at start.
        memory_budget: Bytes the checkpoints may take in all, in memory or,
            with ``directory``, on disk. The oldest are evicted beyond it,
            except the first and the newest.
        directory: Write the checkpoints to this directory instead of
            holding them in memory.
        compress: Gzip each checkpoint (smaller, slower).
    """

    def __init__(
        self,
        model: Model[Any, Any],
        every: float = DEFAULT_EVERY,
        *,
        memory_budget: int = DEFAULT_BUDGET,
        directory: str | Path | None = None,
        compress: bool = False,
    ) -> None:
        """Prepare to record ``model``; recording starts with ``start()``."""
        if every <= 0:
            raise ValueError(f"Checkpoint interval must be > 0, got {every}")
        self.model = model
        self.every = every
        self.compress = compress
        if directory is None:
            self._ring: MemoryRing | DiskRing = MemoryRing(memory_budget)
        else:
            self._ring = DiskRing(directory, memory_budget)
        self._last: float | None = None

    def __enter__(self) -> Recorder:
        """Start recording."""
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        """Stop recording; the checkpoints stay available."""
        self.stop()

    @property
    def recording(self) -> bool:
        """Whether the model is being recorded now."""
        hook = vars(self.model).get(HOOK)
        return isinstance(hook, _Hook) and hook.recorder is self

    @property
    def steps(self) -> list[float]:
        """The steps that hold a checkpoint, oldest first."""
        return self._ring.steps

    @property
    def span(self) -> tuple[float, float]:
        """The first and last step ``at`` can return."""
        if self._last is None:
            raise ValueError("Nothing recorded yet: call start() first.")
        return self.steps[0], self._last

    @property
    def nbytes(self) -> int:
        """The bytes the checkpoints take, in memory or on disk."""
        return self._ring.nbytes

    def start(self) -> None:
        """Checkpoint the model now and every ``every`` time units from here."""
        hook = vars(self.model).get(HOOK)
        if isinstance(hook, _Hook):
            raise RuntimeError("The model is already being recorded.")
        vars(self.model)[HOOK] = _Hook(self)
        self._capture()

    def stop(self) -> None:
        """Stop recording; ``at`` and ``branch`` keep working."""
        if self.recording:
            del vars(self.model)[HOOK]

    def checkpoint(self) -> None:
        """Checkpoint the model now, after changing it from outside the run.

        Replay reruns the model's own dynamics only: a change made between
        two ``run_for`` calls, such as setting an agent attribute, reaches
        ``at`` for the steps after the next checkpoint. Call this right after
        such a change so that every later step includes it.
        """
        self._capture()

    def at(self, step: float) -> Model[Any, Any]:
        """A new model in the state of the recorded run at ``step``.

        The nearest checkpoint at or before ``step`` is restored and run on to
        ``step``. The model is independent of the recorded one and of the
        checkpoints, and its scenario can be changed (see the time travel
        guide for what that means).

        Raises:
            ValueError: If ``step`` is outside ``span``.
        """
        first, last = self.span
        if not first <= step <= last:
            raise ValueError(f"Step {step} is outside the recorded span {self.span}.")
        base = max(s for s in self.steps if s <= step)
        model = model_from_bytes(self._ring.get(base), f"checkpoint at {base}")
        if step > base:
            model._advance_time(step)
        return thaw(model)

    def branch(
        self, step: float, n: int, *, reseed: bool = False
    ) -> list[Model[Any, Any]]:
        """``n`` independent models, all in the state of the run at ``step``.

        Without ``reseed`` every branch continues the same random streams, so
        identical runs stay identical until you change one. With ``reseed``,
        branch ``i`` is reseeded from ``scenario.seed_sequence.spawn(n)[i]``:
        the child seeds ``Scenario.spawn_replications(n)`` uses.
        """
        state = checkpoint_bytes(self.at(step))
        models = [thaw(model_from_bytes(state)) for _ in range(n)]
        if reseed and models:
            children = models[0].scenario.seed_sequence.spawn(n)
            for model, child in zip(models, children):
                reseed_model(model, child)
        return models

    def _advance(self, until: float) -> None:
        """Advance the model to ``until`` in pieces ending at checkpoints."""
        model = self.model
        plain = _plain_advance(model)
        if until <= model.time:
            plain(until)  # warns, as it does without a recorder
            return
        index = math.floor(model.time / self.every) + 1
        while index * self.every <= until:
            plain(float(index * self.every))
            self._capture()
            index += 1
        if model.time < until:
            plain(until)
        self._last = model.time

    def _capture(self) -> None:
        """Add a checkpoint of the model now, without the recorder's hook."""
        model = self.model
        hook = vars(model).pop(HOOK, None)
        try:
            data = checkpoint_bytes(model, compress=self.compress)
        finally:
            if hook is not None:
                vars(model)[HOOK] = hook
        self._ring.add(model.time, data)
        self._last = model.time
