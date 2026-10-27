"""Array backends: numpy on the CPU, CuPy on CUDA GPUs, JAX on CPU, CUDA or Metal.

A :class:`Backend` wraps one array library (``backend.xp``, used like numpy)
and adds the handful of operations whose spelling differs between them: a
functional scatter (JAX arrays are immutable), per-bin sums, the Philox
rounds, device synchronisation and free memory. Everything in ``modelly.gpu``
is written against it, so one setting moves a model between devices::

    backend = get_backend("cupy")      # or "jax", "numpy", "auto"
    MODELLY_BACKEND=cupy python run.py # the same, for get_backend()

A backend that cannot be loaded falls back to numpy with a
:class:`BackendFallbackWarning` (``strict=True`` raises instead), so a model
written for the GPU always runs. CuPy and JAX are imported only when their
backend is requested: ``import modelly`` and the numpy backend never load them.
"""

from __future__ import annotations

import importlib
import os
import warnings
from typing import Any

import numpy as np

from modelly.gpu.philox import philox4x32

ENV_VARIABLE = "MODELLY_BACKEND"
NUMPY, CUPY, JAX, AUTO = "numpy", "cupy", "jax", "auto"
# Where each backend's class lives; imported on request only.
BACKEND_CLASSES = {
    CUPY: "modelly.gpu.cupy_backend:CupyBackend",
    JAX: "modelly.gpu.jax_backend:JaxBackend",
}
AUTO_ORDER = (CUPY, JAX)


class BackendUnavailableError(ImportError):
    """The requested array backend cannot be loaded on this machine."""


class BackendFallbackWarning(RuntimeWarning):
    """A GPU backend was requested but numpy runs instead."""


class Backend:
    """The numpy backend, and the interface the GPU backends implement.

    Attributes:
        name: ``"numpy"``, ``"cupy"`` or ``"jax"``.
        xp: the array namespace.
        gpu: whether arrays live on an accelerator.
    """

    name = NUMPY
    gpu = False
    wide = True  # 64-bit integers available for the Philox products
    compacts = True  # data-dependent shapes are cheap (no compilation per shape)
    fused = False  # uniform_at, bits_at and bounded_at are single kernels

    def __init__(self) -> None:
        """Bind numpy as the array namespace."""
        self.xp = np

    @property
    def float_dtype(self) -> Any:
        """The widest float the backend computes in (float64, or float32 on 32-bit JAX)."""
        return self.xp.float64

    @property
    def int_dtype(self) -> Any:
        """The widest integer the backend stores (int64, or int32 on 32-bit JAX)."""
        return self.xp.int64

    @property
    def device(self) -> str:
        """A short description of where the arrays live."""
        return "cpu"

    def asarray(self, values: Any, dtype: Any = None) -> Any:
        """``values`` as an array of this backend (copied to the device if needed)."""
        return self.xp.asarray(values, dtype=dtype)

    def to_numpy(self, array: Any) -> np.ndarray:
        """A numpy copy (or view) of ``array`` on the host."""
        return np.asarray(array)

    def put(self, array: Any, index: Any, values: Any) -> Any:
        """A copy of ``array`` with ``array[index] = values``; ``array`` is unchanged."""
        result = array.copy()
        result[index] = values
        return result

    def segment_add(self, index: Any, weights: Any, n: int) -> Any:
        """``out[b]`` = sum of ``weights`` where ``index == b``, for ``b < n``.

        Integer and boolean weights give exact integer sums (below 2**53);
        float sums may differ in the last bits between devices, which add in a
        different order.
        """
        xp = self.xp
        sums = xp.bincount(index, weights=weights, minlength=n)
        if weights.dtype.kind in "biu":
            return xp.rint(sums).astype(self.int_dtype)
        return sums

    def bincount(self, index: Any, n: int) -> Any:
        """How many times each bin ``b < n`` occurs in ``index``."""
        return self.xp.bincount(index, minlength=n).astype(self.int_dtype)

    def argsort_stable(self, values: Any) -> Any:
        """Indices that sort ``values``, equal values keeping their order."""
        return self.xp.argsort(values, kind="stable")

    def philox(self, block: Any, words: tuple[int, int, int], key: tuple[int, int]):
        """Philox4x32-10 at counters ``(block, *words)``: four uint32 arrays."""
        return philox4x32((block, *words), key, self.xp, wide=self.wide)

    def synchronize(self, array: Any = None) -> None:
        """Wait for the device to finish (for timing); numpy is always finished."""

    def free_bytes(self) -> int:
        """Bytes available for new arrays: available host memory for numpy (0 if unknown)."""
        try:
            import psutil  # noqa: PLC0415 - optional (the bench extra)
        except ImportError:
            return _sysconf_available()
        return int(psutil.virtual_memory().available)

    def __repr__(self) -> str:
        """The backend's name and device."""
        return f"<Backend {self.name} on {self.device}>"


def _sysconf_available() -> int:
    """Available physical memory from ``os.sysconf`` (POSIX), or 0 where it is missing."""
    try:
        return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, ValueError, OSError):
        return 0


def _load(name: str) -> Backend:
    """Instantiate the backend ``name``; BackendUnavailableError when it cannot load."""
    if name == NUMPY:
        return Backend()
    if name not in BACKEND_CLASSES:
        raise ValueError(f"unknown backend {name!r}: {NUMPY}, {CUPY}, {JAX} or {AUTO}")
    module_name, class_name = BACKEND_CLASSES[name].split(":")
    try:
        return getattr(importlib.import_module(module_name), class_name)()
    except (ImportError, RuntimeError, OSError) as error:
        raise BackendUnavailableError(
            f"backend {name!r} unavailable: {error}"
        ) from error


def _auto() -> Backend:
    """The first GPU backend that loads with a GPU device, else numpy."""
    for name in AUTO_ORDER:
        try:
            backend = _load(name)
        except BackendUnavailableError:
            continue
        if backend.gpu:
            return backend
    return Backend()


def get_backend(name: str | Backend | None = None, strict: bool = False) -> Backend:
    """The array backend ``name``: ``"numpy"``, ``"cupy"``, ``"jax"`` or ``"auto"``.

    Args:
        name: a backend name, a Backend (returned as is), or None for the
            ``MODELLY_BACKEND`` environment variable (numpy when unset).
        strict: raise BackendUnavailableError instead of falling back to numpy.
    """
    if isinstance(name, Backend):
        return name
    name = (name or os.environ.get(ENV_VARIABLE) or NUMPY).lower()
    if name == AUTO:
        return _auto()
    try:
        return _load(name)
    except BackendUnavailableError as error:
        if strict:
            raise
        warnings.warn(
            f"{error}; running on numpy instead", BackendFallbackWarning, stacklevel=2
        )
        return Backend()


def available_backends() -> list[str]:
    """The backends that load on this machine, numpy first."""
    found = [NUMPY]
    for name in BACKEND_CLASSES:
        try:
            _load(name)
        except BackendUnavailableError:
            continue
        found.append(name)
    return found
