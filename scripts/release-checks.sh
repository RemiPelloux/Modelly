#!/usr/bin/env bash
# Release checks that run on this machine instead of hosted CI. Modelly runs only the
# Release (on a tag) and docs workflows on GitHub Actions; every other workflow is
# manual-only, and these stages do their work locally before a release.
#
#   bash scripts/release-checks.sh               # every stage
#   bash scripts/release-checks.sh --list        # stage names
#   bash scripts/release-checks.sh mpi bundles   # a subset
#
# Stages:
#   mpi       split runs and partition independence, with mpirun when mpi4py is installed
#   slurm     job arrays through the stand-in sbatch and qsub (a real cluster: sinfo on PATH)
#   bundles   run, bundle and verify three studies, then verify them unpacked elsewhere
#   pyodide   the pure wheel imports and runs an example in Pyodide under node
#   browser   every example and zoo model from its export-web site in headless Chromium
#   studio    Studio's views in headless Chromium, Firefox and WebKit (Playwright browsers;
#             MODELLY_BROWSER_EXECUTABLE points WebKit at a wrapper where its libraries lack)
#   docs      the documentation builds with warnings as errors
#   native    the compiled modules and their pure-Python twins, a wheel that must compile
#             them all, and the free-threaded build when FT_PYTHON names its interpreter
#   bench     every playbook against the last release (or AGAINST=x.y.z), results identical
# A stage whose tool is missing prints what to install and fails: a release needs them all.
# macOS and Windows are not covered here; say so in the release notes.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
PYTHON="${PYTHON:-.venv/bin/python}"
WORK="$ROOT/build/release-checks"
STAGES=(native mpi slurm bundles pyodide browser studio docs bench)
STEPS=20
SEED=7
PYODIDE_VERSION=314.0.7  # keep in step with modelly.web.export.PYODIDE_VERSION
WEBKIT_WRAPPER="${WEBKIT_WRAPPER:-$ROOT/build/webkit-libs/MiniBrowser}"
STUDIES=(
  "boltzmann modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
  "schelling modelly.examples.basic.schelling.model:Schelling"
  "llm modelly.examples.llm.llm_opinions.model:LLMOpinions"
)

need() {
  command -v "$1" >/dev/null || { echo "missing: $1 ($2)"; return 1; }
}

stage_native() {
  local suites=(tests/native tests/time)
  "$PYTHON" -m pytest -q -W error "${suites[@]}" &&
    MODELLY_PURE_PYTHON=1 "$PYTHON" -m pytest -q -W error "${suites[@]}" &&
    MODELLY_REQUIRE_NATIVE=1 "$PYTHON" -m pip wheel --no-deps -q -w "$WORK/native" . || return 1
  if [[ -n "${FT_PYTHON:-}" ]]; then
    PYTHONPATH="$ROOT" "$FT_PYTHON" -m pytest -q "${suites[@]}"
  else
    echo "note: FT_PYTHON unset, the free-threaded build is not checked"
  fi
}

stage_bench() {
  local previous="${AGAINST:-$(git describe --tags --abbrev=0 | sed 's/^v//')}"
  "$PYTHON" -m modelly bench --against "$previous" --rounds 9 --core 3 --no-record
}

stage_mpi() {
  "$PYTHON" -c "import mpi4py" 2>/dev/null || echo "note: mpi4py missing, the MPI tests skip"
  "$PYTHON" -m pytest -q -W error tests/distributed tests/determinism/test_determinism_partition.py
}

stage_slurm() {
  "$PYTHON" -m pytest -q -rs -W error tests/experiments/executors/test_cluster_scripts.py
}

stage_bundles() {
  local runs="$WORK/runs" review="$WORK/review"
  rm -rf "$runs" "$review" && mkdir -p "$runs" "$review" || return 1
  for spec in "${STUDIES[@]}"; do
    set -- $spec
    "$PYTHON" -m modelly run "$2" --steps "$STEPS" --seed "$SEED" --out "$runs/$1" &&
      "$PYTHON" -m modelly bundle "$runs/$1" --out "$runs/$1.zip" &&
      "$PYTHON" -m zipfile -e "$runs/$1.zip" "$review/$1" &&
      "$PYTHON" -m modelly verify "$review/$1/manifest.json" | grep -q "outputs match" || return 1
  done
}

stage_pyodide() {
  need node "Node.js 20 or later" && need npm "comes with Node.js" || return 1
  local dir="$WORK/pyodide" wheel
  rm -rf "$dir/dist" && mkdir -p "$dir" || return 1
  MODELLY_PURE_PYTHON=1 "$PYTHON" -m pip wheel --no-deps -q -w "$dir/dist" . || return 1
  wheel="$(ls "$dir"/dist/*-py3-none-any.whl 2>/dev/null | head -1)"
  [[ -n "$wheel" ]] || { echo "no pure wheel in $dir/dist"; return 1; }
  # ES modules resolve "pyodide" from the script's folder, so the script runs from there.
  cp scripts/pyodide-smoke.mjs "$dir/" &&
    (cd "$dir" && npm install --no-save --no-audit --no-fund "pyodide@$PYODIDE_VERSION" >/dev/null &&
      node pyodide-smoke.mjs "$wheel")
}

stage_browser() {
  "$PYTHON" -c "import playwright" 2>/dev/null ||
    { echo "missing: playwright for Python (pip install playwright; playwright install chromium)"; return 1; }
  MODELLY_BROWSER_TESTS=1 "$PYTHON" -m pytest -q tests/web/test_browser.py
}

stage_studio() {
  "$PYTHON" -c "import playwright" 2>/dev/null ||
    { echo "missing: playwright for Python (pip install playwright; playwright install)"; return 1; }
  local browser executable
  for browser in chromium firefox webkit; do
    executable=""
    # Playwright's WebKit lacks libraries on some distributions; docs/studio.md explains
    # the wrapper, kept out of git under build/.
    [[ $browser == webkit && -x "$WEBKIT_WRAPPER" ]] && executable="$WEBKIT_WRAPPER"
    MODELLY_BROWSER="$browser" MODELLY_BROWSER_EXECUTABLE="$executable" \
      "$PYTHON" -m pytest -q tests/studio/test_studio_browsers.py || return 1
  done
}

stage_docs() {
  "$PYTHON" -m sphinx -b html -W --keep-going -q docs "$WORK/docs"
}

if [[ "${1:-}" == "--list" ]]; then
  printf '%s\n' "${STAGES[@]}"
  exit 0
fi
selected=("$@")
[[ ${#selected[@]} -eq 0 ]] && selected=("${STAGES[@]}")
mkdir -p "$WORK"
failed=()
for name in "${selected[@]}"; do
  [[ " ${STAGES[*]} " == *" $name "* ]] || { echo "Unknown stage: $name (see --list)" >&2; exit 2; }
  echo "==> $name"
  if "stage_$name"; then echo "<== $name: passed"; else echo "<== $name: failed"; failed+=("$name"); fi
  echo
done
echo "release-checks summary"
for name in "${selected[@]}"; do
  if [[ " ${failed[*]-} " == *" $name "* ]]; then echo "  failed  $name"; else echo "  passed  $name"; fi
done
[[ ${#failed[@]} -eq 0 ]]
