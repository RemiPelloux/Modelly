"""The ``modelly-gpu`` playbook variants: the CPU fallback runs, and GPUs give its integers."""

import importlib
import sys
from pathlib import Path

import pytest

from modelly.gpu.backend import ENV_VARIABLE

PLAYBOOKS = Path(__file__).resolve().parents[2] / "benchmarks" / "playbooks"
SEED = 3
# JAX compiles per array shape and a cohort table changes shape every day, so the
# cross-backend runs are kept short (see docs/gpu.md, "JAX and changing shapes").
EQUALITY_STEPS = 25


@pytest.fixture(scope="module")
def registry():
    """The playbook registry, with the playbook directory importable."""
    sys.path.insert(0, str(PLAYBOOKS))
    yield importlib.import_module("registry").PLAYBOOKS
    sys.path.remove(str(PLAYBOOKS))


def run(registry, playbook, steps=None):
    """Build and simulate the playbook's modelly-gpu variant at the small size."""
    spec = registry[playbook]
    module = importlib.import_module(f"{playbook}.{spec['variants']['modelly-gpu']}")
    model = module.build(seed=SEED, **spec["params"], **spec["sizes"]["small"])
    return module.simulate(model, steps or spec["steps"])


@pytest.mark.parametrize("playbook", ["grid_epidemic", "insect_cohorts"])
def test_numpy_fallback_runs_and_is_deterministic(registry, playbook, monkeypatch):
    """On numpy the variant runs and repeats itself for a seed."""
    monkeypatch.setenv(ENV_VARIABLE, "numpy")
    first = run(registry, playbook, steps=30)
    assert first == run(registry, playbook, steps=30)
    assert first["population"] > 0


@pytest.mark.parametrize("playbook", ["grid_epidemic", "insect_cohorts"])
def test_gpu_backends_give_the_cpu_statistics(
    registry, playbook, other_backend, monkeypatch
):
    """Same seed: the same integer state, hence the same statistics, as on numpy."""
    monkeypatch.setenv(ENV_VARIABLE, "numpy")
    expected = run(registry, playbook, EQUALITY_STEPS)
    monkeypatch.setenv(ENV_VARIABLE, other_backend.name)
    assert run(registry, playbook, EQUALITY_STEPS) == expected
