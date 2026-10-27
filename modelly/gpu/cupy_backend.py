"""The CuPy backend: arrays on an NVIDIA GPU through CUDA (Linux and Windows).

``pip install "modelly-abm[gpu]"`` installs ``cupy-cuda13x``, whose wheels carry
the CUDA runtime and NVRTC: no CUDA toolkit is needed, only the NVIDIA driver.
The Philox rounds run in compiled elementwise kernels, one per kind of draw
(words, uniforms, bounded integers), each computing an element's block and
converting it in registers; everything else is CuPy's numpy-compatible API.
CuPy is imported when the backend is created, never by ``import modelly``.

The kernels follow the numpy code of ``modelly.gpu.philox`` and
``modelly.gpu.streams`` operation for operation (integer arithmetic, and
float conversions that are exact), so they give numpy's numbers bit for bit.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from modelly._optional import require
from modelly.gpu.backend import CUPY, Backend
from modelly.gpu.philox import CUDA_PHILOX

COUNTER_IN = "uint32 c1, uint32 c2, uint32 c3, uint32 k0, uint32 k1"


def _rounds(block: str) -> str:
    """The kernel line that runs Philox on the counter ``(block, c1, c2, c3)``."""
    return f"unsigned int x[4] = {{{block}, c1, c2, c3}}; modelly_philox(x, k0, k1);"


UNIFORM64 = (
    "unsigned int lane = (pos & 1) * 2;"
    "u = ((double)(x[lane] >> 5) * 67108864.0 + (double)(x[lane + 1] >> 6))"
    " * 1.1102230246251565e-16;"
)
NEIGHBOR_START = (
    "long long first = indptr[row], degree = indptr[row + 1] - first;"
    "unsigned int pos = start + (unsigned int)i;"
)
NEIGHBOR_PICK = (
    "out = degree > 0"
    " ? indices[first + __umulhi(x[pos & 3], (unsigned int)degree)] : row;"
)
# Each kernel: (inputs, outputs, body). Position ``pos``; k elements per 128-bit block.
KERNELS = {
    "block": (
        "uint32 block, " + COUNTER_IN,
        "uint32 r0, uint32 r1, uint32 r2, uint32 r3",
        _rounds("block") + "r0 = x[0]; r1 = x[1]; r2 = x[2]; r3 = x[3];",
    ),
    "bits": (
        "uint32 pos, " + COUNTER_IN,
        "uint32 w",
        _rounds("pos >> 2") + "w = x[pos & 3];",
    ),
    "bounded": (
        "uint32 pos, uint32 high, " + COUNTER_IN,
        "int64 v",
        _rounds("pos >> 2") + "v = (long long)__umulhi(x[pos & 3], high);",
    ),
    "uniform32": (
        "uint32 pos, " + COUNTER_IN,
        "float32 u",
        _rounds("pos >> 2") + "u = (float)(x[pos & 3] >> 8) * 5.9604644775390625e-08f;",
    ),
    "uniform64": (
        "uint32 pos, " + COUNTER_IN,
        "float64 u",
        _rounds("pos >> 1") + UNIFORM64,
    ),
    "neighbor": (
        "int64 row, raw int64 indptr, raw int64 indices, uint32 start, " + COUNTER_IN,
        "int64 out",
        NEIGHBOR_START + _rounds("pos >> 2") + NEIGHBOR_PICK,
    ),
}


class CupyBackend(Backend):
    """Arrays on the current CUDA device, through CuPy."""

    name = CUPY
    gpu = True
    fused = True

    def __init__(self) -> None:
        """Import CuPy, check a device answers and declare the Philox kernels."""
        cupy = require("cupy", "gpu")
        if cupy.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("CuPy found no CUDA device")
        self.xp = cupy
        self._kernels = {
            name: cupy.ElementwiseKernel(
                params, out, body, f"modelly_{name}", preamble=CUDA_PHILOX
            )
            for name, (params, out, body) in KERNELS.items()
        }

    @property
    def device(self) -> str:
        """The CUDA device's name."""
        cupy = self.xp
        properties = cupy.cuda.runtime.getDeviceProperties(cupy.cuda.Device().id)
        name = properties["name"]
        return name.decode() if isinstance(name, bytes) else str(name)

    def to_numpy(self, array: Any) -> np.ndarray:
        """Copy ``array`` from the device to a numpy array."""
        return self.xp.asnumpy(array)

    def argsort_stable(self, values: Any) -> Any:
        """CuPy's argsort is a stable radix sort."""
        return self.xp.argsort(values, kind="stable")

    def _scalars(self, words: tuple[int, int, int], key: tuple[int, int]) -> list:
        """The counter words and the key as uint32 kernel arguments."""
        return [self.xp.uint32(value) for value in (*words, *key)]

    def _positions(self, positions: Any) -> Any:
        """``positions`` as a uint32 device array."""
        return self.xp.asarray(positions, dtype=self.xp.uint32)

    def philox(self, block: Any, words: tuple[int, int, int], key: tuple[int, int]):
        """The Philox rounds at every block, one kernel launch: four word arrays."""
        block = self._positions(block)
        return self._kernels["block"](block, *self._scalars(words, key))

    def bits_at(self, positions: Any, words: tuple, key: tuple) -> Any:
        """The uint32 word of the elements at ``positions`` (four per block)."""
        return self._kernels["bits"](
            self._positions(positions), *self._scalars(words, key)
        )

    def bounded_at(self, positions: Any, high: Any, words: tuple, key: tuple) -> Any:
        """``high * word >> 32`` for the elements at ``positions``."""
        high = self.xp.asarray(high, dtype=self.xp.uint32)
        positions = self._positions(positions)
        return self._kernels["bounded"](positions, high, *self._scalars(words, key))

    def uniform_at(self, positions: Any, words: tuple, key: tuple, single: bool) -> Any:
        """Uniforms of the elements at ``positions``: float32 (24 bits) or float64 (53)."""
        kernel = self._kernels["uniform32" if single else "uniform64"]
        return kernel(self._positions(positions), *self._scalars(words, key))

    def neighbor_at(self, rows: Any, csr: tuple, words: tuple, key: tuple) -> Any:
        """``random_neighbor`` in one kernel: the uniform pick and the gather, per row.

        ``csr`` is ``(indptr, indices)`` as int64 device arrays; element ``i``
        draws the bounded integer at position ``i``, as the generic path does.
        """
        indptr, indices = csr
        rows = self.xp.asarray(rows, dtype=self.xp.int64)
        scalars = self._scalars(words, key)
        return self._kernels["neighbor"](
            rows, indptr, indices, self.xp.uint32(0), *scalars
        )

    def synchronize(self, array: Any = None) -> None:
        """Wait for every kernel queued on the current device."""
        self.xp.cuda.Device().synchronize()

    def free_bytes(self) -> int:
        """Free device memory plus what CuPy's pool holds and can reuse."""
        cupy = self.xp
        free, _total = cupy.cuda.runtime.memGetInfo()
        pool = cupy.get_default_memory_pool()
        return int(free + pool.free_bytes())
