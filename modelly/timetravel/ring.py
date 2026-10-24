"""Checkpoint rings: the recorded checkpoints of a run, within a byte budget.

A ring maps a step (the model's ``time`` when the checkpoint was taken) to the
bytes of a checkpoint file. When the ring holds more bytes than its budget it
drops its oldest checkpoints, except the first one, so a recorded run can
always be rewound to where recording started.

:class:`MemoryRing` keeps the bytes in memory. :class:`DiskRing` writes each
checkpoint to its own file through a temporary file and ``os.replace``, which
is atomic on Windows, macOS and Linux: a file in the ring is always whole.
"""

from __future__ import annotations

import os
from pathlib import Path

# The first checkpoint and the newest one are never evicted.
KEEP = 2
SUFFIX = ".ckpt"
PARTIAL = ".partial"


class _Ring:
    """Steps and sizes of the checkpoints held, with eviction to the budget."""

    def __init__(self, budget: int) -> None:
        """Hold checkpoints up to ``budget`` bytes in all."""
        if budget <= 0:
            raise ValueError(f"The checkpoint budget must be > 0, got {budget}")
        self.budget = budget
        self._sizes: dict[float, int] = {}

    @property
    def steps(self) -> list[float]:
        """The steps held, oldest first."""
        return list(self._sizes)

    @property
    def nbytes(self) -> int:
        """The bytes held in all."""
        return sum(self._sizes.values())

    def add(self, step: float, data: bytes) -> None:
        """Hold ``data`` as the checkpoint of ``step``, then keep to the budget."""
        self._store(step, data)
        self._sizes[step] = len(data)
        steps = self.steps
        while self.nbytes > self.budget and len(steps) > KEEP:
            self.discard(steps.pop(1))

    def discard(self, step: float) -> None:
        """Drop the checkpoint of ``step``."""
        self._sizes.pop(step)

    def get(self, step: float) -> bytes:
        """The checkpoint bytes of ``step``."""
        raise NotImplementedError

    def _store(self, step: float, data: bytes) -> None:
        """Keep ``data`` for ``step``."""
        raise NotImplementedError


class MemoryRing(_Ring):
    """Checkpoints held in memory as bytes."""

    def __init__(self, budget: int) -> None:
        """Hold checkpoints up to ``budget`` bytes of memory."""
        super().__init__(budget)
        self._data: dict[float, bytes] = {}

    def get(self, step: float) -> bytes:
        """The checkpoint bytes of ``step``."""
        return self._data[step]

    def discard(self, step: float) -> None:
        """Drop the checkpoint of ``step``."""
        super().discard(step)
        del self._data[step]

    def _store(self, step: float, data: bytes) -> None:
        """Keep ``data`` for ``step`` in memory."""
        self._data[step] = data


class DiskRing(_Ring):
    """Checkpoints held as files ``step-<time>.ckpt`` in one directory.

    Each file is an ordinary checkpoint that ``Model.load`` reads. Files left
    when the ring is dropped stay on disk; evicted ones are deleted.
    """

    def __init__(self, directory: str | Path, budget: int) -> None:
        """Hold checkpoints up to ``budget`` bytes of disk in ``directory``."""
        super().__init__(budget)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, step: float) -> Path:
        """The file that holds the checkpoint of ``step``."""
        return self.directory / f"step-{step!r}{SUFFIX}"

    def get(self, step: float) -> bytes:
        """The checkpoint bytes of ``step``, read from its file."""
        return self.path(step).read_bytes()

    def discard(self, step: float) -> None:
        """Drop the checkpoint of ``step`` and delete its file."""
        super().discard(step)
        self.path(step).unlink(missing_ok=True)

    def _store(self, step: float, data: bytes) -> None:
        """Write ``data`` to a temporary file, then move it into place."""
        final = self.path(step)
        partial = final.with_name(final.name + PARTIAL)
        partial.write_bytes(data)
        os.replace(partial, final)
