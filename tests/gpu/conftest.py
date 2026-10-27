"""Backends for the GPU tests: numpy always, CuPy and JAX where they load.

``other_backend`` runs a test once per non-numpy backend and skips the
backends that do not load here. JAX runs with 64-bit types enabled for the duration
of the test (``jax.enable_x64``), so its floats can be compared bit for bit
with numpy's; the 32-bit mode has its own tests. JAX does not preallocate most of the GPU
here, so a GPU benchmark or the CuPy tests can run beside it.
"""

import contextlib
import os

import pytest

os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

from modelly.gpu.backend import CUPY, JAX, BackendUnavailableError, get_backend

GPU_NAMES = (CUPY, JAX)


def load(name):
    """The backend ``name``, or a skip when it does not load here (checked per test).

    Loading at collection would import CuPy and JAX into every test session.
    """
    try:
        return get_backend(name, strict=True)
    except BackendUnavailableError as error:
        pytest.skip(str(error))


@contextlib.contextmanager
def wide(name):
    """64-bit JAX while the block runs; nothing for the other backends."""
    if name != JAX:
        yield
        return
    import jax  # noqa: PLC0415 - only when the JAX backend loads

    with jax.enable_x64(True):
        yield


@pytest.fixture(params=GPU_NAMES)
def other_backend(request):
    """A non-numpy backend (64-bit for JAX), or a skip when it does not load."""
    with wide(request.param):
        yield load(request.param)


@pytest.fixture
def jax_backend():
    """The JAX backend in its default 32-bit mode, or a skip without JAX."""
    return load(JAX)
