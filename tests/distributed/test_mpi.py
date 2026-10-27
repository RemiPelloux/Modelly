"""The MPI backend: ``mpirun -n 2`` and ``-n 4`` give the single-process outputs.

Each case runs ``mpi_run.py`` under ``mpirun`` in a subprocess (the workers
import this checkout's ``modelly`` through ``PYTHONPATH``) and compares the
rows and the agents' state digest rank 0 wrote with a single-process run.
Skipped when mpi4py or mpirun is missing.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from mpi_run import CASES, digest

from modelly.distributed import single_process

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("mpi_run.py")
STEPS = 8
TIMEOUT = 300  # seconds for one mpirun, start-up included

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("mpi4py") is None or shutil.which("mpirun") is None,
    reason="mpi4py or mpirun is missing",
)


def _mpirun(ranks: int, case: str, out: Path) -> None:
    """Run the helper on ``ranks`` ranks; fail with its output if it fails."""
    env = dict(os.environ, PYTHONPATH=str(ROOT), OMPI_MCA_rmaps_base_oversubscribe="1")
    command = ["mpirun", "-n", str(ranks), "--bind-to", "none", "-x", "PYTHONPATH"]
    command += [sys.executable, str(SCRIPT), case, str(STEPS), str(out)]
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("ranks", [2, 4])
@pytest.mark.parametrize("case", sorted(CASES))
def test_mpi_split_equals_one_process(tmp_path, case, ranks):
    """Rows and agent states on ``ranks`` MPI ranks equal one process."""
    out = tmp_path / "out.json"
    _mpirun(ranks, case, out)
    result = json.loads(out.read_text(encoding="utf-8"))
    model_class, scenario, _ = CASES[case](ranks)
    reference = single_process(model_class, scenario, STEPS)
    assert result["rows"] == reference.rows.to_dict(orient="list")
    assert result["states"] == digest(reference.states)


def test_an_error_on_one_rank_stops_every_rank(tmp_path):
    """A failure on the rank owning person 1 is raised on the others too."""
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    command = ["mpirun", "-n", "2", "--bind-to", "none", "-x", "PYTHONPATH"]
    command += [sys.executable, str(SCRIPT), "failing", str(STEPS), str(tmp_path)]
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )
    assert result.returncode != 0
    assert "person 1 cannot advance" in result.stderr
    assert "MPI rank" in result.stderr
