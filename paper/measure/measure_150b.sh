#!/bin/bash
# The reproducibility evidence the paper can give for 1.5.0 without hosted runners: exact
# digests of every golden example on this machine under CPython 3.12, 3.14 and 3.15, compiled
# and pure Python, and the determinism and split-run suites (MPI with 2 and 4 ranks) on Linux.
# Run after measure_150.sh; .venv-py312 and .venv-py314 built like .venv.
set -u
cd "$(dirname "$0")/../.." || exit 1
OUT=paper/data/local_digests
mkdir -p "$OUT"
stamp() { echo "== $1  $(date -u +%H:%M:%S)  $(git rev-parse --short HEAD)  code-diff-vs-v1.5.0: $(git diff --name-only v1.5.0 -- modelly | wc -l)"; }
for v in .venv-py312 .venv-py314 .venv; do
  py=$($v/bin/python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
  for build in compiled pure; do
    stamp "golden digests, CPython $py, $build"
    if [ $build = pure ]; then export MODELLY_PURE_PYTHON=1; else unset MODELLY_PURE_PYTHON; fi
    $v/bin/python -m modelly.dev golden --json > "$OUT/digests-linux-x86_64-$py-$build.json" 2> "$OUT/digests-linux-x86_64-$py-$build.err"
    echo "exit $?"
  done
done
unset MODELLY_PURE_PYTHON
for v in .venv-py312 .venv-py314 .venv; do
  stamp "determinism and split runs, $v"
  $v/bin/python -m pytest -q -p no:cacheprovider tests/determinism tests/distributed 2>&1 | tail -2
done
stamp "done"
