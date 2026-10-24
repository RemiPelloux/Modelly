# Playbooks: the same eight models on Mesa 2.3 and Modelly

Eight workloads, each written twice: once for Mesa 2.3 the way its API intends
(per-agent methods, `MultiGrid` / `SingleGrid` / `ContinuousSpace` /
`NetworkGrid`, the `PropertyLayer`, `RandomActivation`, the `DataCollector`),
once for Modelly the way *its* API intends (`Column` state, vectorised phases,
`CellIndex`, one KD-tree per step). The two are the same
model in distribution, which the runner checks; they are different programs on
purpose, which is the point: the comparison measures what each framework lets
a modeller write, not interpreter overhead on identical code. For that other
question (a line-by-line port), see `docs/performance.md`.

| playbook | Modelly variant `modelly`: what is an array operation | what stays per agent |
|---|---|---|
| `grid_epidemic` | the random walk (`CellIndex.random_neighbor`), exposure count per cell, infection, recovery | nothing |
| `predator_prey` | movement, energy, grazing (random tie-break), predation (`claim`), deaths, births (one `create_agents` per species), grass regrowth | nothing |
| `flocking` | neighbour pairs (periodic KD-tree), the three steering terms, the move | nothing |
| `network_contagion` | infected-neighbour count (sparse adjacency), infection, recovery, resistance | nothing |
| `insect_cohorts` | survival, ageing, stage transitions, laying | egg creation (`modelly`); nothing (`modelly-cohorts`) |
| `schelling` | same-kind neighbour counts (`counts` + `neighbor_sum`), the moves to random empty cells (a fixed-size pool of empty cells) | nothing |
| `boltzmann_wealth` | who gives in the random order (a fixed point over the drawn order and partners), the exchange, the Gini and wealth records (`DataCollector`, column reporter) | nothing |
| `sugarscape` | visible cells, their sugar and the head of each forager's ranking (segment minima, no sort); eating, metabolism, starvation (`remove_where`), growback on the property layer | the walk to the first free cell (a ranking is sorted only when its head was taken) |

Five playbooks carry a third variant. `grid_epidemic`, `predator_prey`,
`schelling` and `sugarscape` have `modelly-cells`: the same model with Mesa's
data structure, every cell holding the list of its agents, so movement and predation stay per-agent loops and
only the obviously vectorisable phases are arrays. It shows what the layout
alone is worth. In `schelling` that variant holds one resident per cell
(`capacity=1`) and moves each unhappy one to `select_random_empty_cell`, which
the grid answers from its index of empty cells; in `sugarscape` each forager
scans `cell.get_neighborhood(radius=vision)` and reads the `sugar` layer
through the cell. `insect_cohorts` has `modelly-cohorts`, in which one row of
a `CohortTable` (no agent objects) stands for every insect in the same (stage,
age, sex) class and survival is a binomial thinning of the cohort; it has the
same law as the individual models. `docs/vectorised_phases.md` gives the argument for each vectorised
phase, for the predation matching and for the compression, and (§7 to §9) for
the sequential phases of `schelling`, `boltzmann_wealth` and `sugarscape`:
moves to random empty cells, giving and foraging in a random order.

## Running

Mesa 2.3 and Modelly cannot share an environment. The runner starts each run in
the framework's own interpreter:

```bash
python -m venv .venv-mesa2
.venv-mesa2/bin/pip install "mesa==2.3.2" numpy pandas networkx
.venv/bin/python benchmarks/playbooks/compare.py --core 5          # everything, pinned
.venv/bin/python benchmarks/playbooks/compare.py flocking --rounds 5
.venv/bin/python benchmarks/playbooks/worker.py insect_cohorts modelly-cohorts 1 large
```

`MESA_PYTHON` and `MODELLY_PYTHON` override the interpreter paths. The
parameters of every playbook live in `registry.py`; the implementations import
nothing from each other.

## What is measured, and the rules

1. **CPU time of a fresh interpreter**, build plus run, from `time.process_time`
   around the model's `run`; imports excluded. `--core N` pins each run to one
   core with `taskset`. Rounds alternate the implementations, so a load spike
   lands on all of them; every round is reported, not only the best.
2. **Agreement.** Every implementation runs the same seeds at the small size and
   each summary statistic is compared with the Mesa reference by Welch's
   t-test. A p-value below 0.01 is printed in bold in the results. The
   implementations draw their random numbers in different orders, so their
   outputs differ run by run and must agree in distribution.
3. **Determinism.** The first seed is run twice per implementation; the
   statistics must be identical.
4. **Same model on both sides.** Same rules, same phase order, same update
   (synchronous, or one agent at a time in a random order), same parameters,
   same graph (networkx with the same seed), same initial positions and traits
   (numpy with the same seed) where that applies. The Mesa side uses numpy
   where a Mesa modeller would (the grass and sugar layers, the per-boid
   neighbour arithmetic); it is not written to be slow. Where Mesa 2.3's own
   idiom is quadratic for no modelling reason (indexing an `AgentSet` copies
   its keys), the Mesa side keeps a list instead.

Results: `results/README.md` and one JSON per playbook, regenerated by the
runner.
