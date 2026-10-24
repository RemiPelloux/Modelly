"""The job-array task entry point: ``python -m modelly.experiments.worker TASKS [INDEX]``.

``TASKS`` is the ``tasks.json`` a SLURM or PBS executor wrote; ``INDEX`` picks
one task from it (default: ``$SLURM_ARRAY_TASK_ID``, ``$PBS_ARRAY_INDEX`` or
``$PBS_ARRAYID``). The task runs, its Parquet file goes to the store, and the
exit status is 0 when it finished, 1 when it failed (recorded in the store).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from modelly.experiments.tasks import DONE, RunOutcome, RunTask, run_task

EXIT_DONE, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
MAX_ARGUMENTS = 2  # TASKS and INDEX
INDEX_VARIABLES = ("SLURM_ARRAY_TASK_ID", "PBS_ARRAY_INDEX", "PBS_ARRAYID")


def load_tasks(path: str | Path) -> list[RunTask]:
    """The tasks a cluster executor wrote to ``path``."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [RunTask.from_dict(row) for row in rows]


def array_index(argument: str | None = None) -> int:
    """The task index: ``argument``, else the scheduler's array index variable."""
    if argument is not None:
        return int(argument)
    for variable in INDEX_VARIABLES:
        if os.environ.get(variable):
            return int(os.environ[variable])
    raise LookupError(
        f"no task index: pass one or set one of {', '.join(INDEX_VARIABLES)}"
    )


def run_array_task(tasks_file: str | Path, index: int) -> RunOutcome:
    """Run task ``index`` of ``tasks_file`` (what each job-array element does)."""
    return run_task(load_tasks(tasks_file)[index])


def main(argv: list[str] | None = None) -> int:
    """Run one task of a job array; the exit status."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv or len(argv) > MAX_ARGUMENTS:
        sys.stderr.write(
            f"usage: python -m modelly.experiments.worker TASKS [INDEX]\n{__doc__}"
        )
        return EXIT_USAGE
    try:
        index = array_index(argv[1] if len(argv) == MAX_ARGUMENTS else None)
        outcome = run_array_task(argv[0], index)
    except (LookupError, ValueError, OSError) as error:
        sys.stderr.write(f"modelly.experiments.worker: {error}\n")
        return EXIT_USAGE
    if outcome.status == DONE:
        return EXIT_DONE
    sys.stderr.write(outcome.error or "run failed\n")
    return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
