"""SLURM and PBS job arrays run as real job scripts, by stand-in or real schedulers.

``test_cluster.py`` replaces ``subprocess.run`` and runs the array in this process.
Here nothing is patched: ``sbatch`` and ``qsub`` are small executables on ``PATH``
that read the array range from the job script's directives, as the schedulers do,
and run the script with ``bash`` once per element with ``SLURM_ARRAY_TASK_ID`` or
``PBS_ARRAY_INDEX`` set. The generated script itself (shebang, ``set -euo
pipefail``, setup lines, the worker command, the index variable) therefore runs in a
fresh shell and a fresh interpreter for every element, and the results must equal a
serial run.

With ``MODELLY_REAL_SCHEDULER=slurm`` (the ``slurm`` CI job, on a single-node SLURM
cluster) or ``pbs``, the same check runs against the real ``sbatch`` or ``qsub``.
"""

import os
import shutil
import stat
import sys
import textwrap
from pathlib import Path

import pytest

from modelly.experiments.executors.cluster import PBSExecutor, SlurmExecutor
from tests.experiments.executors.shared import MAX_PARALLEL, experiment

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")

ROOT = Path(__file__).resolve().parents[3]
REAL = os.environ.get("MODELLY_REAL_SCHEDULER", "")
EXECUTORS = {"slurm": SlurmExecutor, "pbs": PBSExecutor}
REAL_TIMEOUT = 900  # seconds a real cluster may take to run the array
REAL_POLL = 2.0
SETUP_MARK = "setup ran"
JOB_IDS = {"slurm": "4242", "pbs": "4242.local"}

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="job scripts are bash scripts, run on a Linux cluster",
)

# What the stand-in scheduler does: the directive giving the array, the index variable.
STAND_IN = textwrap.dedent(
    """\
    #!{python}
    import os, re, subprocess, sys
    from pathlib import Path

    ARRAYS = {{"sbatch": (r"^#SBATCH --array=(\\d+)-(\\d+)", "SLURM_ARRAY_TASK_ID"),
              "qsub": (r"^#PBS -J (\\d+)-(\\d+)", "PBS_ARRAY_INDEX")}}
    pattern, variable = ARRAYS[Path(sys.argv[0]).name]
    script = sys.argv[-1]
    found = re.search(pattern, Path(script).read_text(encoding="utf-8"), re.M)
    indices = range(int(found[1]), int(found[2]) + 1) if found else [0]
    for index in indices:
        subprocess.run(["bash", script], env={{**os.environ, variable: str(index)}})
    print("4242;local" if variable.startswith("SLURM") else "4242.local")
    """
)


@pytest.fixture
def stand_ins(tmp_path, monkeypatch):
    """``sbatch`` and ``qsub`` stand-ins first on PATH; this checkout importable."""
    folder = tmp_path / "bin"
    folder.mkdir()
    for name in ("sbatch", "qsub"):
        path = folder / name
        path.write_text(STAND_IN.format(python=sys.executable), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    return folder


def _run_through(executor, tmp_path):
    """Results through ``executor`` and serially (data frames), and the run count."""
    reference = experiment(tmp_path / "serial")
    reference.run("serial")
    split = experiment(tmp_path / executor.name)
    report = split.run(executor, max_parallel=MAX_PARALLEL)
    runs = len(split.tasks())
    assert report.ok and report.done == runs
    return split.results().df(), reference.results().df(), runs


@pytest.mark.parametrize("name", sorted(EXECUTORS))
def test_job_script_runs_every_element_in_a_fresh_shell(name, tmp_path, stand_ins):
    """Each array element runs the written script in bash: the serial numbers."""
    log = tmp_path / "setup.log"
    setup = [f"echo {SETUP_MARK} >> {log}"]
    executor = EXECUTORS[name](
        python=sys.executable, setup=setup, wait=True, poll_interval=0, timeout=60
    )
    split, serial, runs = _run_through(executor, tmp_path)
    assert split.equals(serial)
    assert log.read_text(encoding="utf-8").count(SETUP_MARK) == runs
    assert executor.job_id == JOB_IDS[name]


def test_a_failing_element_is_recorded_not_lost(tmp_path, stand_ins):
    """An element whose worker raises leaves a failure record the poll reads."""
    from modelly.experiments import Experiment, ScenarioSpace  # noqa: PLC0415
    from tests.experiments.models import Walk  # noqa: PLC0415

    failing = Experiment(
        Walk, ScenarioSpace(fail=True, n=2), outputs="mean", steps=3, store=tmp_path
    )
    executor = SlurmExecutor(python=sys.executable, wait=True, poll_interval=0)
    report = failing.run(executor)
    assert len(report.failed) == 1 and "asked to fail" in report.failed[0].error


@pytest.mark.skipif(REAL not in EXECUTORS, reason="no real scheduler to submit to")
def test_a_real_scheduler_gives_the_serial_numbers(tmp_path, monkeypatch):
    """On a real SLURM or PBS cluster (CI), the array equals the serial run."""
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    executor = EXECUTORS[REAL](
        python=sys.executable, wait=True, poll_interval=REAL_POLL, timeout=REAL_TIMEOUT
    )
    split, serial, _ = _run_through(executor, tmp_path)
    assert split.equals(serial)
