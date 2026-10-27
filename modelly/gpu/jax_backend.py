"""The JAX backend: CPU everywhere, CUDA on Linux and Windows, Metal on macOS.

JAX runs on whatever device its installed plugins provide: ``pip install
"jax[cuda13]"`` for NVIDIA GPUs, ``jax-metal`` for Apple GPUs (where available;
untested in Modelly's own runs), the CPU otherwise. JAX arrays are immutable,
so every update in ``modelly.gpu`` is functional (``put`` returns a new array).

Without ``jax.config.update("jax_enable_x64", True)`` JAX has no 64-bit types:
floats are float32, integers int32, and the Philox products go through 16-bit
halves. The integers drawn are the same either way; uniforms are float32 with
24 random bits, the same values numpy gives for ``random(n, dtype=float32)``.
"""

from __future__ import annotations

from functools import partial
from typing import Any

import numpy as np

from modelly._optional import require
from modelly.gpu.backend import JAX, Backend
from modelly.gpu.philox import philox4x32

CPU_PLATFORM = "cpu"
BYTES_LIMIT, BYTES_IN_USE = "bytes_limit", "bytes_in_use"


class JaxBackend(Backend):
    """Arrays on JAX's default device."""

    name = JAX
    compacts = False  # every new shape compiles: keep shapes fixed, mask instead

    def __init__(self) -> None:
        """Import JAX, find its default device and jit the Philox rounds."""
        jax = require("jax", "diff")
        self.jax = jax
        self.xp = jax.numpy
        self.wide = bool(jax.config.jax_enable_x64)
        self._device = jax.devices()[0]
        self.gpu = self._device.platform != CPU_PLATFORM
        rounds = partial(philox4x32, xp=self.xp, wide=self.wide)
        self._philox = jax.jit(rounds, static_argnums=1)

    @property
    def float_dtype(self) -> Any:
        """float64 with ``jax_enable_x64``, else float32."""
        return self.xp.float64 if self.wide else self.xp.float32

    @property
    def int_dtype(self) -> Any:
        """int64 with ``jax_enable_x64``, else int32."""
        return self.xp.int64 if self.wide else self.xp.int32

    @property
    def device(self) -> str:
        """The platform and kind of JAX's default device (``cuda``, ``METAL``, ``cpu``)."""
        return f"{self._device.platform}: {self._device.device_kind}"

    def to_numpy(self, array: Any) -> np.ndarray:
        """Copy ``array`` to the host."""
        return np.asarray(self.jax.device_get(array))

    def put(self, array: Any, index: Any, values: Any) -> Any:
        """``array`` with ``array[index] = values``, as a new array."""
        return array.at[index].set(values)

    def segment_add(self, index: Any, weights: Any, n: int) -> Any:
        """Per-bin sums by a scatter-add; integer weights stay integers (exact)."""
        xp = self.xp
        dtype = self.int_dtype if weights.dtype.kind in "biu" else weights.dtype
        return xp.zeros(n, dtype=dtype).at[index].add(weights.astype(dtype))

    def bincount(self, index: Any, n: int) -> Any:
        """Occurrences of each bin by a scatter-add of ones."""
        return self.xp.zeros(n, dtype=self.int_dtype).at[index].add(1)

    def argsort_stable(self, values: Any) -> Any:
        """A stable argsort (JAX's keyword differs from numpy's)."""
        return self.xp.argsort(values, stable=True)

    def philox(self, block: Any, words: tuple[int, int, int], key: tuple[int, int]):
        """The jitted Philox rounds (compiled once per key and shape)."""
        block = self.xp.asarray(block, dtype=self.xp.uint32)
        counter = (block, *(self.xp.uint32(word) for word in words))
        return self._philox(counter, tuple(key))

    def synchronize(self, array: Any = None) -> None:
        """Block until ``array`` (or every pending computation) is ready."""
        if array is not None:
            array.block_until_ready()
            return
        self.jax.effects_barrier()

    def free_bytes(self) -> int:
        """Free memory of the device; available host memory on the CPU."""
        stats = self._device.memory_stats() if self.gpu else None
        if not stats or BYTES_LIMIT not in stats:
            return Backend.free_bytes(self)
        return int(stats[BYTES_LIMIT] - stats.get(BYTES_IN_USE, 0))
