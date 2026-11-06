#!/bin/bash
# Every measurement the paper reports, on Modelly 1.5.0's code (the tag v1.5.0; main differs
# from it only in docs, checked at every stage). Phase 1 at a fixed frequency (performance
# governor, turbo off, CPU 2), then restore; the later phases are not timing-sensitive per core.
# Needs SUDO_PW in the environment (to set the governor and turbo), Linux with intel_pstate,
# .venv, .gpu-venv (CUDA) and the Mesa baselines installed; one heavy job at a time.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/bin/python
A=paper/scripts/agreement.py
OUT=build/logs/m150
mkdir -p "$OUT"
OLD_GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
OLD_TURBO=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo)
sw() { printf '%s\n' "$SUDO_PW" | sudo -S -p '' sh -c "echo $1 > $2"; }
restore() {
  for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do sw "$OLD_GOV" "$g"; done
  sw "$OLD_TURBO" /sys/devices/system/cpu/intel_pstate/no_turbo
  echo "restored: $(cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor) no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo)"
}
codediff() { git diff --name-only v1.5.0 -- modelly benchmarks paper/scripts tools pyproject.toml | wc -l; }
stamp() { echo "== $1  $(date -u +%H:%M:%S)  load $(cut -d' ' -f1-3 /proc/loadavg)  $(git rev-parse --short HEAD)  code-diff-vs-v1.5.0: $(codediff)"; }
quiet() { grep -v 'RuntimeWarning\|round [0-9]'; }

# --- phase 1: timings at a fixed frequency -------------------------------------------------
trap restore EXIT
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do sw performance "$g"; done
sw 1 /sys/devices/system/cpu/intel_pstate/no_turbo
sleep 5
echo "governor $(cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor) no_turbo $(cat /sys/devices/system/cpu/intel_pstate/no_turbo) cur $(cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_cur_freq) kHz"
stamp "playbooks, session 1 (10 rounds, CPU 2)"
$PY benchmarks/playbooks/compare.py --rounds 10 --core 2 2>&1 | quiet | tail -20
rm -rf paper/data/playbooks_session1 && cp -r benchmarks/playbooks/results paper/data/playbooks_session1
stamp "migrated models"
$PY paper/scripts/migrated.py --rounds 10 --core 2 2>&1 | quiet | tail -20
stamp "mesa examples"
$PY benchmarks/mesa_examples/run.py --rounds 10 --seeds 100 --core 2 --agree-cores 8-15 2>&1 | quiet | tail -20
stamp "mesa-frames threads"
$PY paper/scripts/frames_threads.py 2>&1 | quiet | tail -6
$PY paper/scripts/frames_threads.py --rounds 5 --cores 0-3 2>&1 | quiet | tail -6
stamp "three sizes (5 rounds, CPU 2)"
$PY paper/scripts/sizes.py run --rounds 5 --core 2 2>&1 | quiet | tail -12
stamp "ablation ladder"
$PY paper/scripts/ablation.py run --rounds 10 --core 2 2>&1 | quiet | tail -12
stamp "sweep end to end"
$PY paper/scripts/sweep_e2e.py run --rounds 5 --core 2 2>&1 | quiet | tail -8
stamp "three CPython versions"
$PY paper/scripts/python_versions.py run --rounds 5 --core 2 2>&1 | quiet | tail -12
stamp "ODE per agent against solve_ivp, and the within-host model"
taskset -c 2 $PY benchmarks/ode/compare.py 2>&1 | tail -20
taskset -c 2 $PY benchmarks/ode/within_host.py 2>&1 | tail -10
stamp "playbooks, session 2 (10 rounds, CPU 2)"
$PY benchmarks/playbooks/compare.py --rounds 10 --core 2 2>&1 | quiet | tail -20
restore
trap - EXIT

# --- phase 2: GPU, scaling, statistics -------------------------------------------------------
stamp "gpu (equality, 5 rounds, 10 million agents)"
$PY benchmarks/playbooks/gpu_speedup.py --equality --n 10000000 --side 1000 > "$OUT/gpu_equality.json" 2> "$OUT/gpu_equality.err"
$PY benchmarks/playbooks/gpu_speedup.py --n 10000000 --side 1000 --rounds 5 > "$OUT/gpu_speedup5.json" 2> "$OUT/gpu_speedup5.err"
tail -3 "$OUT/gpu_speedup5.json"
: > "$OUT/gpu_small.jsonl"
for seed in 1 2 3; do
  for spec in "grid_epidemic modelly .venv" "grid_epidemic modelly-gpu .gpu-venv" \
              "insect_cohorts modelly-cohorts .venv" "insect_cohorts modelly-gpu .gpu-venv"; do
    set -- $spec
    (cd benchmarks/playbooks && MODELLY_BACKEND=cupy PYTHONPATH=$PWD/../.. ../../$3/bin/python worker.py $1 $2 $seed large) \
      | grep '^RESULT ' | sed 's/^RESULT //' >> "$OUT/gpu_small.jsonl"
  done
done
stamp "weak scaling"
$PY benchmarks/distributed/weak_scaling.py --backend mpi --workers 1 2 4 8 12 16 --people 10000 --steps 20 --out paper/data/weak_mpi_10k.json 2>&1 | tail -8
$PY benchmarks/distributed/weak_scaling.py --backend mpi --workers 1 2 4 8 --people 40000 --steps 10 --out paper/data/weak_mpi_40k.json 2>&1 | tail -6
$PY benchmarks/distributed/weak_scaling.py --backend dask --workers 1 2 4 8 --people 10000 --steps 20 --out paper/data/weak_dask_10k.json 2>&1 | tail -6

stamp "agreement studies"
$PY $A run --size small --jobs 12 && $PY $A analyse --size small
$PY $A run --size large --seeds 50 --jobs 12 && $PY $A analyse --size large --seeds 50
$PY $A run --variants mesa3 frames --tag small_baselines --jobs 12 && $PY $A analyse --tag small_baselines
NP="--variants mesa3np --playbooks grid_epidemic schelling boltzmann_wealth"
$PY $A run $NP --tag small_mesa3np --jobs 12 && $PY $A analyse --tag small_mesa3np
$PY $A run --size large --variants mesa3np --playbooks grid_epidemic --tag large_grid_mesa3np --jobs 12 && $PY $A analyse --tag large_grid_mesa3np
$PY $A run --seeds 300 --seed-base 10000 --playbooks schelling --variants mesa3 frames modelly modelly-cells --tag schelling300_new --jobs 12 && $PY $A analyse --tag schelling300_new
$PY $A run --size large --seeds 200 --seed-base 10000 --playbooks grid_epidemic --tag large_grid200_new --jobs 12 && $PY $A analyse --tag large_grid200_new
stamp "trajectories"
$PY paper/scripts/trajectories.py run --seeds 100 --jobs 12 && $PY paper/scripts/trajectories.py analyse
stamp "KD-tree flocking against Mesa 3.5"
$PY paper/scripts/kdtree_equality.py --small 100 --large 10 --jobs 12 2>&1 | tail -3
stamp "virus example: trace and replications"
$PY paper/scripts/virus_trace.py --seeds 10 2>&1 | tail -5
$PY benchmarks/mesa_examples/run.py --only virus_on_network --rounds 1 --seeds 300 --seed-base 10000 --jobs 12 --output paper/data/mesa_examples_virus300_new.json 2>&1 | tail -4
$PY benchmarks/mesa_examples/run.py --only virus_on_network --rounds 1 --seeds 1000 --seed-base 20000 --jobs 12 --output paper/data/mesa_examples_virus1000_new.json 2>&1 | tail -4

stamp "calibration: recovery, prior coverage, particle sweep, weights"
$PY paper/scripts/recovery.py run --replicates 200 --jobs 12 && $PY paper/scripts/recovery.py analyse
$PY paper/scripts/prior_coverage.py run --replicates 500 --jobs 12 2>&1 | quiet | tail -6
$PY paper/scripts/prior_coverage.py run --replicates 500 --jobs 12 --particles 100 2>&1 | quiet | tail -6
$PY paper/scripts/abc_sweep.py run --particles 30 60 100 200 --replicates 500 --jobs 12 2>&1 | quiet | tail -4 && $PY paper/scripts/abc_sweep.py analyse | tail -12
$PY paper/scripts/abc_weights_check.py 2>&1 | tail -4
cp benchmarks/ode/results.json paper/data/ode_compare.json && cp benchmarks/ode/within_host.json paper/data/ode_within_host.json
stamp "paper data scripts"
for s in odes decisions cohort_counterexample sobol_scramblings assimilation ishigami graph_cut; do
  $PY paper/scripts/$s.py > "$OUT/$s.txt" 2>&1; echo "$s exit $?"
done

stamp "100 million rows"
mkdir -p "$OUT/rows"
for spec in "memmap 16G" "memory 16G" "memmap 3G" "memory 3G"; do
  set -- $spec
  dir=$(mktemp -d -p build) || exit 1
  systemd-run --user --scope -q -p MemoryMax=$2 -p MemorySwapMax=0 --unit="m150-$1-$2-$$" \
    $PY benchmarks/large_columns.py --rows 100000000 --steps 3 --storage $1 --dir "$dir" > "$OUT/rows/rows_$1_$2.txt" 2>&1
  echo "$1 $2 exit $? ; $(tail -4 "$OUT/rows/rows_$1_$2.txt" | tr '\n' ' ')"
  rm -rf "$dir"
done

stamp "active learning against hypercubes"
export OPENBLAS_NUM_THREADS=1
$PY benchmarks/emulate/active_vs_lhs.py bass --runs 60 > "$OUT/active_bass.txt" 2>&1 &
$PY benchmarks/emulate/active_vs_lhs.py branin --criterion ivr --runs 80 > "$OUT/active_branin_ivr.txt" 2>&1 &
$PY benchmarks/emulate/active_vs_lhs.py branin --criterion variance --runs 80 > "$OUT/active_branin_var.txt" 2>&1 &
$PY benchmarks/emulate/active_vs_lhs.py ishigami --criterion ivr --runs 100 > "$OUT/active_ishigami_ivr.txt" 2>&1 &
$PY benchmarks/emulate/active_vs_lhs.py ishigami --criterion variance --runs 100 > "$OUT/active_ishigami_var.txt" 2>&1 &
wait
unset OPENBLAS_NUM_THREADS
tail -n 3 "$OUT"/active_*.txt

# --- phase 3: GPU tests, the browser, accessibility, the test suite ----------------------------
stamp "GPU and differentiable tests on CuPy and CUDA JAX"
.gpu-venv/bin/python -m pytest -q -p no:cacheprovider tests/gpu tests/diff 2>&1 | tail -3
stamp "every model from its export in the browser (pure wheel)"
bash scripts/release-checks.sh browser 2>&1 | tail -8
stamp "the compiled WebAssembly wheel"
PYB=build/release/pyb
[ -x "$PYB/bin/pyodide" ] || { uv venv -q -p 3.14 "$PYB" && uv pip install -q -p "$PYB/bin/python" pyodide-build \
  && PATH=$PYB/bin:$PATH pyodide xbuildenv install 314.0.7 && PATH=$PYB/bin:$PATH pyodide xbuildenv install-emscripten; } > "$OUT/pyb.log" 2>&1
rm -rf build/release/wasm150
PATH=$PWD/$PYB/bin:$PATH bash scripts/build-wasm-wheel.sh build/release/wasm150 > "$OUT/wasm_build.log" 2>&1; echo "wasm build exit $?"
W=$(ls build/release/wasm150/*pyemscripten*wasm32.whl 2>/dev/null | head -1); echo "wheel $W"
[ -n "$W" ] && MODELLY_BROWSER_TESTS=1 MODELLY_WASM_WHEEL=$W $PY -m pytest -q -p no:cacheprovider tests/web/test_browser.py -k wasm 2>&1 | tail -4
stamp "browser first load (full reports)"
rm -rf build/sites
mkdir -p "$OUT/browser_load"
$PY -m modelly export-web modelly.zoo.age_seir.model:AgeSEIR --out build/sites/age_seir > /dev/null &&
  $PY -m modelly export-web modelly.zoo.forest_fire.model:ForestFire --out build/sites/forest_fire > /dev/null || echo "export failed"
for site in age_seir forest_fire; do
  for profile in none broadband-50 fast-4g; do
    $PY tools/web/measure_load.py build/sites/$site --profile $profile --runs 3 > "$OUT/browser_load/load_${site}_${profile}.json" 2>&1
    echo "$site $profile exit $?"
  done
done
stamp "accessibility (axe-core)"
bash scripts/release-checks.sh a11y 2>&1 | tail -8
stamp "determinism suite"
$PY -m pytest -q -p no:cacheprovider tests/determinism 2>&1 | tail -3
stamp "test suite and coverage"
$PY -m pytest -q -rfE -p pytest_cov --cov --cov-report=xml:"$OUT/coverage.xml" -W error -W default::PendingDeprecationWarning 2>&1 | grep -v '^modelly/\|^tools/\|^benchmarks/' | tail -30
$PY -c "import xml.etree.ElementTree as E;r=E.parse('$OUT/coverage.xml').getroot();print('line-rate',r.get('line-rate'),'branch-rate',r.get('branch-rate'))"
stamp "done"
