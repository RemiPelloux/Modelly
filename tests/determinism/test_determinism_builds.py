"""Compiled and pure Python give the same runs; a resumed run equals a straight one.

A run saved at mid-run and loaded again must finish exactly as one that never stopped.
"""

import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

import pytest

from modelly import Model
from modelly._native import sets
from modelly.core.exceptions import CheckpointError
from modelly.dev.digest import run_digest
from modelly.dev.golden import EXAMPLES

ROOT = Path(__file__).resolve().parents[2]
PURE = "MODELLY_PURE_PYTHON"


def _digests_in_subprocess(pure: bool) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != PURE}
    if pure:
        env[PURE] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "modelly.dev", "golden", "--json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def test_compiled_and_pure_python_give_identical_runs():
    """Every example's exact digest is the same with and without the C modules."""
    pure = _digests_in_subprocess(pure=True)
    compiled = _digests_in_subprocess(pure=False)
    assert pure == compiled
    assert set(pure) == {e.name for e in EXAMPLES if e.available()}


def test_this_process_matches_a_fresh_interpreter():
    """The build under test (compiled when built) agrees with the other build."""
    here = {e.name: run_digest(e.run()) for e in EXAMPLES if e.available()}
    assert here == _digests_in_subprocess(pure=sets.NATIVE)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.name)
def test_resume_from_checkpoint_is_the_same_run(example, tmp_path):
    """Save at mid-run, load, finish: same data and final state as a straight run.

    An example listed as not checkpointable must still refuse to save, so the entry is
    removed as soon as it can be saved.
    """
    if not example.available():
        pytest.skip(f"{example.name} needs {', '.join(example.requires)}")
    straight = example.run()
    half = example.steps // 2
    first = example.build()
    first.run_for(half)
    if example.no_checkpoint:
        with pytest.raises((CheckpointError, pickle.PicklingError)):
            first.save(tmp_path / "mid.ckpt")
        pytest.skip(f"{example.name}: {example.no_checkpoint}")
    first.save(tmp_path / "mid.ckpt")
    resumed = Model.load(tmp_path / "mid.ckpt")
    resumed.run_for(example.steps - half)
    assert run_digest(resumed) == run_digest(straight)
