# Session 7: experiments, sweeps and replications

**Zoo models:** [Deffuant](../zoo/deffuant.md), [Hegselmann-Krause](../zoo/hegselmann_krause.md),
[Axelrod](../zoo/axelrod.md)

## Goals

- Design a parameter sweep with replications, each run with its own independent seed.
- Run it in parallel with `modelly.batch.run_grid` on Windows, macOS and Linux.
- Report a result with its spread across seeds, not one lucky run.

**Before the session:** the [sociology tutorial](../tutorials/domains/sociology.md).

## Exercises

**7.1** Sweep the Deffuant confidence bound over 0.05, 0.1, 0.2 and 0.3 with ten replications
each using `run_grid`, and plot the mean and standard deviation of the cluster count.

<details>
<summary>Solution</summary>

Put the run function in an importable file, `sweep.py`, so that worker processes can import
it (Windows and macOS start workers with `spawn`):

```python
# sweep.py
from modelly.batch import run_grid
from modelly.zoo.deffuant.model import Deffuant, DeffuantScenario


def run(task):
    model = Deffuant(DeffuantScenario(rng=task["seed"], epsilon=task["epsilon"]))
    model.run()
    return {"clusters": model.n_clusters()}


if __name__ == "__main__":
    frame = run_grid(run, {"epsilon": [0.05, 0.1, 0.2, 0.3]}, replicates=10, seed=1)
    print(frame.groupby("epsilon")["clusters"].agg(["mean", "std"]))
```

Run it with `python sweep.py` (bash and PowerShell alike).

</details>

**7.2** Are the seeds of `run_grid` the same when you run with one worker and with four?
Why does it matter?

<details>
<summary>Solution</summary>

Yes: `grid_tasks` derives every task's seed from `numpy.random.SeedSequence(seed).spawn`,
before any work is distributed. The results therefore do not depend on the machine or the
number of processes, and anybody can rerun one task alone.

</details>

**7.3** Do the same sweep for Hegselmann-Krause. Which model reaches consensus at a smaller
confidence bound?

<details>
<summary>Solution</summary>

Replace the model and scenario in `run` with `HegselmannKrause` and `HKScenario`. Both
reach consensus between about 0.2 and 0.3 for uniform initial opinions; compare the means
at 0.2 with their standard deviations before calling one smaller.

</details>

**7.4** For Axelrod, sweep `traits` over 2, 5, 10, 15 and 30 with five seeds each. Between
which values does the number of regions take off?

<details>
<summary>Solution</summary>

```python
from modelly.zoo.axelrod.model import Axelrod, AxelrodScenario


def run(task):
    model = Axelrod(AxelrodScenario(rng=task["seed"], traits=task["traits"]))
    model.run()
    return {"regions": model.n_regions()}
```

On a 10 x 10 grid with five features, one or a few regions up to about 10 traits, then a
sharp rise: the finite-size trace of the order-disorder transition of Castellano, Marsili and
Vespignani.

</details>
