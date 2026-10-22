# Mesa baseline: the medfly ABM reference workload

This directory holds the **"before" side of the performance story**: a
fruit-fly (medfly) invasion-control agent-based model written against the
**Mesa 2.3 API**, plus a harness that times it.

The model is a French agronomy study — strawberry and cherry orchards, sterile
insect technique (TIS) release budgets, female remating behaviour, fruit
rotting and larval pressure — and it is a genuinely heavy ABM: a cherry season
creates on the order of 3 000 agents per step.

Nothing in Modelly imports this. It exists so that claims like "Modelly is
faster" have a number attached, measured on the same machine with the same
workload.

## The notebook is not committed

`Notebook_ABM_TIS_Mis_A_Jour.ipynb` (~4.4 MB, 25 cells) is gitignored on
purpose: it is research code with outputs baked in, not library code. Drop it
in this directory to use the harness, or point `--notebook` at it:

```
benchmarks/mesa_baseline/
├── README.md              # this file (tracked)
├── run_baseline.py        # timing harness (tracked)
└── Notebook_ABM_TIS_Mis_A_Jour.ipynb   # reference model (gitignored)
```

## Setup

Mesa 2 and Modelly cannot share an environment, because this is exactly the
API that Mesa 3 broke (`Agent(unique_id, model)` and `Model.next_id()` are
gone). The dedicated environment lives at the repo root:

```bash
python -m venv .venv-mesa2
.venv-mesa2/bin/pip install "mesa==2.3.2" numpy pandas matplotlib seaborn \
    jupyterlab ipykernel
.venv-mesa2/bin/python -m ipykernel install --user --name mesa2-baseline \
    --display-name "Python 3 — Mesa 2.3 (baseline)"
```

Installed and verified here: Mesa 2.3.2, numpy 2.5.4, pandas 3.1.0,
matplotlib 3.11.2, seaborn 0.13.2, JupyterLab 4.6.4, ipykernel 7.4.0.
The notebook uses no removed pandas/seaborn/matplotlib APIs, so current
versions of the analysis stack work with Mesa 2.3.

### Interactive use (the notebook as a playbook)

```bash
cd benchmarks/mesa_baseline
../../.venv-mesa2/bin/jupyter lab Notebook_ABM_TIS_Mis_A_Jour.ipynb
```

Pick the **"Python 3 — Mesa 2.3 (baseline)"** kernel. The notebook is the
playbook: run cells top to bottom and each section produces its own tables and
figures (cell 7 writes `resultats_experience_factorielle.csv`, cell 12 writes
`dynamiques_temporelles_journalieres.csv`).

Neither environment is committed: `.venv-mesa2/` is gitignored, and so are the
notebook and everything it writes.

## Running

### The full notebook — this is the one that matters

Every simulation in the study is mandatory, so the authoritative run executes
**every cell**, in order, in one shared namespace:

```bash
cd benchmarks/mesa_baseline
MPLBACKEND=Agg ../../.venv-mesa2/bin/python run_baseline.py --full
```

That produces the factorial experiment (144 seasons), the fruit-status
dynamics (20 seasons), the daily population dynamics (60 seasons), and all
figures — **~2 hours** on this machine. Run it from this directory so the CSVs
(`resultats_experience_factorielle.csv`, `dynamiques_temporelles_journalieres.csv`)
land next to the notebook, where the plotting cells look for them. The
`*.csv`, `*.log` and `*.json` outputs are gitignored along with the notebook.

Results are reproducible from the seeds baked into the notebook (`base_seed=42`,
`seed=42 + rep * 1000 + ...`); `FORCE_RERUN = True` in cell 7 means the
factorial is recomputed from scratch rather than loaded from cache.

### Timing individual seasons

These modes are for measurement only (they run no plots and no CSVs):

```bash
.venv-mesa2/bin/python benchmarks/mesa_baseline/run_baseline.py              # both crops
.venv-mesa2/bin/python benchmarks/mesa_baseline/run_baseline.py --crop cherry -r 3
.venv-mesa2/bin/python benchmarks/mesa_baseline/run_baseline.py --factorcrop --crop cherry
```

They execute cells 0–5 (imports, crop parameters, agents, model, TIS
calendars) and then drive `RematingModel` directly. A *season* is the unit:
100 steps for strawberry, 25 for cherry.

## Measured numbers

AMD64 Linux, Python 3.15, `mesa==2.3.2`, wild = 10 males / 10 females, no
sterile release unless stated. One season each.

| Crop | Steps | Time | Notes |
| --- | --- | --- | --- |
| strawberry | 100 | **1.4 s** | 30 fruits/day, ~115 fruits alive at end |
| cherry | 25 | **38 s** | invasion 3 |
| cherry | 25 | **54 s** | invasion 10 |
| cherry | 25 | **94 s** | invasion 30 |
| cherry | 25 | **40 s** | budget 600 sterile males |

The notebook's default factorial is 2 crops × 3 invasions × 4 budgets ×
2 remating modes × 3 replicates = **144 seasons**, which extrapolates to
roughly **1–2 hours** of wall clock. Cherry dominates it completely: 72 cherry
seasons at 40–95 s each against 72 strawberry seasons at 1.4 s.

## Why cherry is slow (and why it matters here)

Profiling a 3-step cherry season (`cProfile`, ~4.5 s total):

```
ncalls  tottime  cumtime  function
     3    0.194    4.462  <string>:98(step)          # RematingModel.step
  9192    0.726    4.165  mesa/agent.py:105(__init__) # AgentSet construction
  9192    3.434    3.436  weakref.py:410(update)     # WeakKeyDictionary
```

`RematingModel.step` contains:

```python
agents = list(self.agents)
...
for a in agents:
    if a in self.agents:  # <- one fresh AgentSet per agent
        a.step()
```

On Mesa 2.3.2 that `self.agents` property *rebuilds* the whole `AgentSet` from
`model.agents_` on every access, because the cached `_agents` attribute is
never assigned (`Model.__init__` sets `agents_` instead). With ~3 000 agents
that is ~3 000 `WeakKeyDictionary` rebuilds of ~3 000 entries per step — the
season is quadratic in population, and the actual biology is a rounding error
next to it.

This is the concrete gap Modelly closes:

- `Model.agents` is a stored `AgentSet`, not a property that rebuilds;
- membership is an O(1) dict lookup, not a rebuilt weak-key table;
- `AgentSet.select` / `shuffle` / `groupby` run at C level over a snapshot.

So when you compare, compare **season time**, not step count — a cherry season
should stop scaling with the square of the agent population.
