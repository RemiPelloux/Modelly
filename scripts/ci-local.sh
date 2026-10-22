#!/usr/bin/env bash
# Local CI gate (pelloux-guidelines.md §8): lint, format, test, audit — in order.
#
#   bash scripts/ci-local.sh             # every stage
#   bash scripts/ci-local.sh --list      # stage names
#   bash scripts/ci-local.sh lint audit  # a subset
#
# Uses .venv/bin when it exists, otherwise python3 and ruff from PATH.
# tests/visualization and tests/examples need the optional solara extra and
# are skipped here; the hosted build workflow still runs them.
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

STAGES=(lint format test audit)

run_stage() {
  case "$1" in
    lint)   "$RUFF" check . ;;
    format) "$RUFF" format --check . ;;
    test)   "$PYTHON" -m pytest -q --ignore=tests/visualization --ignore=tests/examples ;;
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
