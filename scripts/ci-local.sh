#!/usr/bin/env bash
# Local CI gate (pelloux-guidelines.md §8): lint, format, types, test, audit — in order.
#
#   bash scripts/ci-local.sh             # every stage
#   bash scripts/ci-local.sh --list      # stage names
#   bash scripts/ci-local.sh lint audit  # a subset
#
# Tests run with warnings as errors, as in the hosted build workflow.
# Uses .venv/bin when it exists, otherwise python3 and ruff from PATH.
# tests/viz and tests/examples need the optional solara extra and
# are skipped when it is missing; the hosted build workflow always runs them.
# The types stage runs mypy in strict mode on the packages [tool.mypy] in
# pyproject.toml lists: `python -m mypy` when it is installed, else the pinned
# mypy through uvx, else it prints why it is skipped and passes.
# The test stage rewrites docs/images/badges/coverage.svg: commit it with the
# change.
# python -m modelly.dev gate runs the same stages without bash (any OS);
# keep the two in step (tests/test_dev_gate.py checks the stage list).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
  RUFF=.venv/bin/ruff
else
  PYTHON=python3
  RUFF=ruff
fi

STAGES=(lint format types test audit)
MYPY_PIN=mypy==2.4.0  # keep in step with TYPE_CHECKER_PIN in modelly/dev/gate.py
# The test stage measures coverage and refreshes the README badge from it.
BADGE=docs/images/badges/coverage.svg
OPTIONAL_SKIPS=()
if ! "$PYTHON" -c "import solara" 2>/dev/null; then
  OPTIONAL_SKIPS=(--ignore=tests/viz --ignore=tests/examples)
fi

run_stage() {
  case "$1" in
    lint)   "$RUFF" check . ;;
    format) "$RUFF" format --check . ;;
    types)  if "$PYTHON" -c "import mypy" 2>/dev/null; then "$PYTHON" -m mypy
            elif command -v uvx >/dev/null; then uvx "$MYPY_PIN" --python-executable "$PYTHON"
            else echo "types: skipped (mypy not installed: pip install mypy or install uv)"; fi ;;
    test)   "$PYTHON" -m pytest -q -W error -W default::PendingDeprecationWarning -p pytest_cov --cov --cov-report=xml ${OPTIONAL_SKIPS[@]+"${OPTIONAL_SKIPS[@]}"} \
              && "$PYTHON" scripts/coverage_badge.py coverage.xml "$BADGE" ;;
    audit)  bash scripts/audit-pelloux.sh ;;
  esac
}

if [[ "${1:-}" == "--list" ]]; then
  printf '%s\n' "${STAGES[@]}"
  exit 0
fi

selected=("$@")
if [[ ${#selected[@]} -eq 0 ]]; then
  selected=("${STAGES[@]}")
fi
for name in "${selected[@]}"; do
  if [[ " ${STAGES[*]} " != *" $name "* ]]; then
    echo "Unknown stage: $name (see --list)" >&2
    exit 2
  fi
done

failed=()
for name in "${selected[@]}"; do
  echo "==> $name"
  if run_stage "$name"; then
    echo "<== $name: passed"
  else
    echo "<== $name: failed"
    failed+=("$name")
  fi
  echo
done

echo "ci-local summary"
for name in "${selected[@]}"; do
  if [[ " ${failed[*]:-} " == *" $name "* ]]; then
    echo "  failed  $name"
  else
    echo "  passed  $name"
  fi
done
[[ ${#failed[@]} -eq 0 ]]
