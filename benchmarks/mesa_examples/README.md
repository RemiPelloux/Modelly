# Same code on both frameworks: Mesa's own examples

The models here are written by Mesa's developers, not by us. `<example>/original/` holds
`model.py` and `agents.py` copied unmodified from Mesa 3.5.1 (`mesa/examples/{basic,advanced}/`,
Apache-2.0, see each `NOTICE` and `LICENSE.mesa`). `<example>/port/` is the same copy after
`python -m modelly.migrate <example>/port --write`; each codemod report is kept verbatim in
`codemod_reports/<example>.txt`. The copies are excluded from ruff (`pyproject.toml`) so
they stay byte-for-byte what Mesa ships.

    python benchmarks/mesa_examples/run.py --rounds 10 --seeds 100 --core 2 --agree-cores 8-15
        # paper/data/mesa_examples.json

## What was changed after the codemod

**Relocation step (all ten ports, not asked for by the codemod).** Each upstream `model.py`
imports its agents by absolute path (`from mesa.examples.basic.schelling.agents import ...`).
The codemod rewrites that to `modelly.examples.basic.schelling.agents`. Modelly ships its own
examples under the same names, so the port would silently load Modelly's bundled agents in place
of the copied Mesa ones. The line becomes `from .agents import ...`, so each port runs its own
`agents.py`. The originals keep their absolute import; it loads the installed Mesa 3.5.1 file,
which is byte-identical to the copy in `original/agents.py` (checked with `cmp`).

**Steps the codemod report asks for.** One was needed: `epstein_civil_violence/port/model.py`
line 121, `self.steps` becomes `self.time`, as the report says. The other flags need no change:
a commented-out line in `pd_grid`, `shuffle_do("step")` lines that are Mesa's own activation,
and the cell method `get_neighborhood` in `epstein_civil_violence`, which the legacy-grid
pattern also matches.

**The codemod fix this study found.** The first ports were made with the codemod of 1.3.2,
which rewrote `mesa.experimental.scenarios`, `mesa.experimental.data_collection` and
`mesa.discrete_space` used as an attribute (`mesa.discrete_space.CellAgent`) to Modelly paths
that do not exist, without reporting them. The codemod now maps the first two to
`modelly.scenarios` and `modelly.data.recorders`, maps dotted names through the same module
table as imports, and reports any Mesa module Modelly lacks instead of rewriting it. The ports
here were regenerated with that codemod; the fix is in the next release.

## Which examples port

| example | result |
|---|---|
| conways_game_of_life, pd_grid, virus_on_network, boid_flockers, boltzmann_wealth_model, schelling, wolf_sheep | the codemod alone (plus the relocation step) |
| epstein_civil_violence | the codemod and the one step its report asks for |
| sugarscape_g1mt | does not port: Mesa's `PropertyLayer` has no Modelly class (the codemod now reports it) |
| alliance_formation | does not port: `create_meta_agent` is not in Modelly's `meta_agents` |

## Sizes and steps

| example | parameters | steps | statistics |
|---|---|---|---|
| conways_game_of_life | Mesa defaults (50 x 50, 20% alive) | 100 | live cells at the end |
| pd_grid | Mesa defaults (50 x 50, Random activation) | 100 | `Cooperating_Agents` |
| virus_on_network | `num_nodes=1000`, other defaults | 200 | `Infected`, `Susceptible`, `Resistant`, `R over S` |
| boid_flockers | Mesa defaults (100 boids) | 100 | polarisation, mean neighbours |
| boltzmann_wealth_model | `n=2500` on 50 x 50 (Mesa's density) | 100 | `Gini` |
| schelling | 50 x 50, other defaults | 50 | `happy`, `pct_happy`, `population`, `minority_pct` |
| wolf_sheep | 50 x 50, 625 sheep and 312 wolves (Mesa's densities) | 100 | `Wolves`, `Sheep`, `Grass` |
| epstein_civil_violence | Mesa defaults | 100 | `active`, `quiet`, `arrested` |

Model reporters are compared at the last step and averaged over the run, because the
predator-prey populations often die out before the end. Where Mesa's defaults run their steps
in well under 0.2 s, the grid is enlarged at the same density so the timing is measurable.

The virus model's default is 10 nodes, whose 200 steps take milliseconds. At 1000 nodes the
steps take about 0.2 s. Mesa's `Network` computes a spring layout for drawing when it is built,
which takes several seconds at 1000 nodes. That cost is in the build, which is not timed. The
graph comes from `nx.erdos_renyi_graph` without a seed, so each run seeds Python's and numpy's
global streams with the run's seed first. Both arms then get the same graph on a given seed.

## Method

The method follows `paper/scripts/ports.py`. Every run is a fresh interpreter that builds the model with `rng=seed`,
calls `gc.collect()` and times `model.step()` N times with `time.process_time()`. Rounds pair
the original with the port on the round's seed and alternate which runs first, pinned with
`taskset -c <core>`. Modelly derives `model.random` from the seed differently from Mesa, so
the statistics are not identical seed by seed. `--seeds K` runs both arms on seeds 2000 to
2000+K-1 at the timed size, and compares each statistic with `compare_one` (a paired t-test,
a KS test and a TOST at 0.5 sd), Holm-corrected over all comparisons (`holm`, both from
`paper/scripts/agreement.py`). A statistic with non-finite values (such as `R over S` when no
agent is susceptible) is recorded as skipped. `--smoke` swaps in small sizes for a quick check.
