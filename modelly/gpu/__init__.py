"""GPU arrays for column phases, cohorts and cell spaces, with one setting.

``get_backend("cupy")`` (CUDA), ``get_backend("jax")`` (CPU, CUDA or Metal) or
``get_backend("numpy")``; ``MODELLY_BACKEND`` sets the default and an
unavailable backend falls back to numpy with a warning. On a backend:

* :class:`DeviceTable`: agent columns on the device (from a ``ColumnTable``);
* :class:`DeviceCohortTable`: ``CohortTable`` with binomial thinning on the device;
* :class:`DeviceCellIndex`: a ``CellIndex``'s counts, neighbour sums and random moves;
* :class:`PhiloxStream`: counter-based random numbers, the same on every backend;
* :func:`plan_memory` and :func:`run_batched`: populations larger than the device.

``import modelly.gpu`` imports neither CuPy nor JAX; a backend imports its
library when it is created. See ``docs/gpu.md``.
"""

from modelly.gpu.backend import (
    Backend,
    BackendFallbackWarning,
    BackendUnavailableError,
    available_backends,
    get_backend,
)
from modelly.gpu.cells import DeviceCellIndex
from modelly.gpu.cohorts import DeviceCohortTable
from modelly.gpu.memory import MemoryPlan, plan_memory, run_batched
from modelly.gpu.philox import philox4x32
from modelly.gpu.streams import PhiloxDraw, PhiloxStream
from modelly.gpu.table import DeviceTable

__all__ = [
    "Backend",
    "BackendFallbackWarning",
    "BackendUnavailableError",
    "DeviceCellIndex",
    "DeviceCohortTable",
    "DeviceTable",
    "MemoryPlan",
    "PhiloxDraw",
    "PhiloxStream",
    "available_backends",
    "get_backend",
    "philox4x32",
    "plan_memory",
    "run_batched",
]
