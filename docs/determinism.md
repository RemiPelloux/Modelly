# Determinism and platforms

The same model, scenario and seed give the same run on Windows, macOS and Linux, with the
compiled modules or in pure Python, straight through or resumed from a checkpoint. This page
says what that promise covers, how the test suite checks it, and the few outputs that are
compared with a tolerance.

## What is promised

- **Same seed, same run.** All randomness comes from `model.random` and `model.rng`, both
  seeded from the scenario. Two runs with the same seed in two processes are identical.
- **Compiled and pure Python agree.** Every C function in `modelly/_native` has a Python twin
  that gives identical results; `MODELLY_PURE_PYTHON=1` selects the twins.
- **A resumed run is the same run.** A model saved at step *k* with `model.save` and loaded
  with `Model.load` finishes exactly as the run that never stopped.
- **Every platform gives the same bytes**, with the exceptions listed below.

## How the suite checks it

`tests/determinism/` runs every bundled example (`modelly/examples/**`, including the spatial
and language-model examples) for a fixed number of steps from seed 42, then takes a SHA-256
digest of:

- the tables its `DataCollector` holds (model variables, and agent variables if any);
- the final state of the model and of every agent (the same snapshot time travel compares:
  public scalars, columns, cell or position) and a digest of both generators' state.

The digest is taken over canonical bytes, never over `repr` or text with platform line
endings: JSON with sorted keys and no whitespace, floats written exactly (`float.hex`),
agents written by `unique_id`, sets and graphs sorted. The suite then checks that:

1. a pure-Python interpreter (`MODELLY_PURE_PYTHON=1`) and a compiled one give the same exact
   digest for every example;
2. a run saved at mid-run, loaded and finished gives the same exact digest as a straight run;
3. every example reproduces the golden digest recorded in `tests/determinism/golden.json`.

The `build` workflow runs the suite on Ubuntu, macOS and Windows, so check 3 compares the three
platforms with each other through the golden file. A `modelly bundle` made on the test machine
is also unpacked and verified with `modelly verify` in a fresh interpreter.

## Outputs compared with a tolerance

IEEE 754 makes `+`, `-`, `*`, `/` and `sqrt` correctly rounded, so they give the same bits on
every platform. The transcendental functions (`exp`, `log`, `pow` with a non-integer exponent,
`arctan2`) and BLAS reductions (`numpy.linalg.norm`) are not: each platform's maths library and
numpy's SIMD kernels may differ in the last bit. Examples whose recorded floats pass through
them are compared at **10 significant digits** in the golden check (`float_digits` in
`golden.json`):

| Example | Why |
|---|---|
| `alliance_formation` | initial power and position from normal draws (the sampler's tails use `log` and `exp`) |
| `boid_flockers` | headings from `arctan2`, distances from `linalg.norm` |
| `epstein_civil_violence` | arrest probability from `exp` |
| `sugarscape_g1mt` | welfare from `pow`, trade price from `exp` and `log` |
| `commuting_city` | destination choice from `exp`, congestion from `pow` |
| `layered_epidemic` | infection probability from `exp` |

`commuting_city` is also compared on the platform that wrote `golden.json` only: its projections
and geometry come from the PROJ and GEOS libraries bundled inside the pyproj and shapely wheels,
and those builds differ between platforms by more than the last digits. On every other
platform its golden check is skipped with that reason; checks 1 and 2 still run everywhere.

Every other example is compared bit for bit. Checks 1 and 2 are always exact: they run on one
machine, where the maths library is the same. A last-bit difference can only change a
discrete decision if a random draw falls exactly on it, which is negligible over the short
golden runs; integers, counts and generator states are never rounded.

Digests also depend on the versions of the libraries that build the model: numpy keeps its
`Generator` streams stable, but a networkx release that changed a graph generator would change
`virus_on_network`. When that happens the golden file is regenerated on purpose.

## Updating the golden digests

A deliberate change to an example or to the framework that changes results needs new
digests:

```bash
python -m modelly.dev golden            # check: prints what differs, exit 1
python -m modelly.dev golden --update   # rewrite tests/determinism/golden.json
python -m modelly.dev golden --json     # this build's exact digests, to compare two machines
```

Commit the new `golden.json` with the change and say in the commit why results changed.

## Examples that cannot be checkpointed yet

Two examples refuse `model.save`, and the suite checks that they still do, so the entry goes
as soon as they can be saved:

- `alliance_formation`: meta-agent classes are created at run time, and pickle cannot find
  them by name;
- `tram_model`: `ContinuousState` rates and `Threshold` callbacks are closures.

## Writing a deterministic model

- Draw every random number from `self.random` or `self.rng`, never from `random` or
  `numpy.random`; pass `seed=self.random` to library generators such as networkx.
- Do not iterate over a `set` of agents or strings whose order matters; sort by `unique_id`.
- Use module-level functions, not lambdas, for reporters and scheduled callbacks, so the
  model can be checkpointed.
- Open text files with `encoding="utf-8"`, and write files you hash with `newline="\n"`.

`modelly lint` finds most of these (see [Checking a model](lint.md)).

## Streams of each agent's own

By default every agent draws from the model's two generators, so what one agent draws depends
on how many numbers the agents before it drew. A model can give each agent generators of its
own instead (provisional, new in 1.4):

```python
class Epidemic(Model):
    agent_streams = True  # agent.random and agent.rng are the agent's own
```

Each agent's seed is derived from the model's seed and the agent's `stream_key()`, its
`unique_id` unless overridden. An agent then draws the same numbers whatever the activation
order and however many agents there are, and checkpoints and pickles continue every stream.
This is what a run split across processes needs, since an agent takes its stream with it.
Override `stream_key()` when the creation order itself could change, for example to key
agents on an identifier read from data. The model's own `self.random` and `self.rng`, and the
bulk draws of columns and cohorts, still use the model's generators. Turning the flag on
changes the numbers a model draws, so results differ from a run without it for the same seed.
