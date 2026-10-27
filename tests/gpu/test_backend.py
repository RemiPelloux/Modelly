"""Backends: selection, the numpy fallback, and the CPU path loading nothing extra."""

import subprocess
import sys

import numpy as np
import pytest

from modelly.gpu import (
    Backend,
    BackendFallbackWarning,
    BackendUnavailableError,
    available_backends,
    get_backend,
)
from modelly.gpu import backend as backend_module


def test_numpy_is_the_default_and_a_backend_passes_through(monkeypatch):
    """No name and no MODELLY_BACKEND: numpy; a Backend instance is returned as is."""
    monkeypatch.delenv(backend_module.ENV_VARIABLE, raising=False)
    backend = get_backend()
    assert backend.name == "numpy" and not backend.gpu and backend.device == "cpu"
    assert get_backend(backend) is backend
    assert "numpy" in repr(backend) and available_backends()[0] == "numpy"


def test_environment_variable_selects_the_backend(monkeypatch):
    """MODELLY_BACKEND names the default backend."""
    monkeypatch.setenv(backend_module.ENV_VARIABLE, "NUMPY")
    assert get_backend().name == "numpy"


def test_unknown_names_are_errors():
    """A misspelt backend is a ValueError, not a silent fallback."""
    with pytest.raises(ValueError):
        get_backend("cuda")


def test_unavailable_backend_falls_back_with_a_warning(monkeypatch):
    """A backend that cannot load gives numpy and a warning, or raises when strict."""
    monkeypatch.setitem(
        backend_module.BACKEND_CLASSES, "cupy", "modelly_no_such_module:X"
    )
    with pytest.warns(BackendFallbackWarning):
        assert get_backend("cupy").name == "numpy"
    with pytest.raises(BackendUnavailableError):
        get_backend("cupy", strict=True)
    assert "cupy" not in available_backends()


def test_auto_without_a_gpu_is_numpy(monkeypatch):
    """``auto`` picks a GPU backend only when one has a GPU device."""
    for name in backend_module.AUTO_ORDER:
        monkeypatch.setitem(
            backend_module.BACKEND_CLASSES, name, "modelly_no_such_module:X"
        )
    assert get_backend("auto").name == "numpy"


def test_numpy_helpers():
    """Put is functional, segment_add keeps integers exact, argsort is stable."""
    backend = Backend()
    array = np.zeros(4, dtype=np.int64)
    assert backend.put(array, [1, 3], 7).tolist() == [0, 7, 0, 7] and array.sum() == 0
    sums = backend.segment_add(np.array([0, 0, 2]), np.array([True, True, False]), 3)
    assert sums.tolist() == [2, 0, 0] and sums.dtype.kind == "i"
    assert backend.argsort_stable(np.array([1, 0, 1, 0])).tolist() == [1, 3, 0, 2]
    assert backend.free_bytes() >= 0
    backend.synchronize()


def test_free_bytes_without_psutil(monkeypatch):
    """Without psutil the host's free memory comes from sysconf (or is unknown)."""
    monkeypatch.setitem(sys.modules, "psutil", None)
    assert Backend().free_bytes() >= 0
    assert backend_module._sysconf_available() >= 0


def test_import_loads_neither_cupy_nor_jax():
    """``import modelly`` and ``import modelly.gpu`` with numpy import no GPU library."""
    code = (
        "import sys, modelly, modelly.gpu, numpy as np\n"
        "from modelly.gpu import PhiloxStream\n"
        "PhiloxStream(1).random(10)\n"
        "print(any(m.split('.')[0] in ('cupy', 'jax', 'jaxlib') for m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"
