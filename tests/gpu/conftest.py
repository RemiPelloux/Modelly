"""Backends for the GPU tests: numpy always, CuPy and JAX where they load.

``other_backend`` runs a test once per non-numpy backend that loads here and
skips when there is none. JAX runs with 64-bit types enabled for the duration
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


def _loads(name):
    """Whether the backend ``name`` loads on this machine."""
    try:
        get_backend(name, strict=True)
    except BackendUnavailableError:
        return False
    return True


AVAILABLE = [name for name in GPU_NAMES if _loads(name)]


@contextlib.contextmanager
def wide(name):
    """64-bit JAX while the block runs; nothing for the other backends."""
    if name != JAX:
        yield
        return
    import jax  # noqa: PLC0415 - only when the JAX backend loads

    with jax.enable_x64(True):
        yield


@pytest.fixture(params=AVAILABLE or [None], ids=AVAILABLE or ["none"])
def other_backend(request):
    """A loaded non-numpy backend (64-bit for JAX), or a skip when none loads."""
    if request.param is None:
        pytest.skip("neither CuPy nor JAX loads here")
    with wide(request.param):
        yield get_backend(request.param, strict=True)


@pytest.fixture
def jax_backend():
    """The JAX backend in its default 32-bit mode, or a skip without JAX."""
    if JAX not in AVAILABLE:
        pytest.skip("JAX is not installed")
    return get_backend(JAX, strict=True)
