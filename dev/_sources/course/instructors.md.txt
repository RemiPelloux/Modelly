# Instructor notes

Notes for teaching the twelve sessions, one 2-hour slot each, and the assessments: the rubric
of the final project and two short graded exercises with their marking criteria.

## The shape of a session

Every session follows the same plan; the notes below say where a session departs from it.

| Time | What |
|---|---|
| 0:00 to 0:25 | Lecture on the topic, from the session's goals |
| 0:25 to 0:45 | Live walk-through of the zoo model, run on the projector |
| 0:45 to 1:45 | Exercises in pairs, about 15 minutes each |
| 1:45 to 2:00 | Two pairs show a solution; the reading for next time |

Run every snippet of the session on the room's machines the day before: the installed
Modelly must be the version these pages were written for. The solutions are folded under each
exercise; tell the students to open them only after a real attempt, and to compare their
numbers, not their code. Most runs take a few seconds; the slowest exercises (10.1 to 10.4)
take five to ten seconds each.

## Session by session

### 1. Agents, a scenario and a step

- **Timing.** A short lecture (15 minutes) and a long walk-through: read `KineticWealth`
  line by line with the class before exercise 1.3.
- **Misconceptions.** That inequality needs unequal agents or rules; that the Gini changes
  with the money per agent (1.2: it barely does); that the four lines of the matching are a
  loop over agents.
- **Check.** In 1.4, that the copy was made with `modelly zoo copy` and the zoo module is
  untouched; that the student can say why `wealth[taker] += amount` is safe (no index repeats).

### 2. Data, seeds and reproducibility

- **Timing.** Spend the walk-through on `model.rng` and the `DataCollector`; 2.2 needs a copy
  of the model, so start it early.
- **Misconceptions.** That `numpy.random.seed(...)` at the top of a script makes a model
  reproducible; that a checkpoint saves only the agents (2.4: it saves both generators); that
  the first steps of a run are part of the stationary average.
- **Check.** In 2.2, that the student reads `MDL001` and can explain it; in 2.3, that the
  mean is taken over the second half only.

### 3. Space, rasters and percolation

- **Timing.** 3.2 runs 40 models; on slow machines let each pair take one raster side and
  pool the results on the board.
- **Misconceptions.** That the threshold is exactly where the fire "always" crosses on a
  finite raster; that `cover` is indexed `[y, x]` like an image (it is `[x, y]`).
- **Check.** In 3.2, that the student sees the uncertain window narrow with the side; in 3.4,
  that the firebreak is wide enough for the neighbourhood used.

### 4. Networks and contact structure

- **Timing.** 4.3 is the longest exercise of the first half of the course; give it 25
  minutes and shorten 4.2 to a discussion.
- **Misconceptions.** That a network with the same mean degree as the mixing behaves the
  same (4.1); that a contact matrix is symmetric whatever the group sizes.
- **Check.** In 4.3, that households and workplaces are built as cliques on the right
  layers; in 4.4, that `group_sizes` matches the groups of the matrix.

### 5. Thinking in arrays: columns and cohorts

- **Timing.** The loop version in 5.2 is slow on a road of 100,000 cells; start the
  profile, then discuss 5.4 while it runs.
- **Misconceptions.** That vectorising never changes a model (5.1: the order of updates
  does); that cohorts are an approximation (they are exact while each row is homogeneous).
- **Check.** In 5.1, that the loop computes all speeds before moving any car and gives the
  same flow for the same seed.

### 6. Validation against theory

- **Timing.** Give the lecture time to derive the final-size relation on the board; the
  exercises are short.
- **Misconceptions.** That a tolerance is chosen until the test passes; that a fixed seed
  makes a loose test safe; that one seed agreeing with the theory validates the model.
- **Check.** That each tolerance in 6.4 is written from a standard deviation, with the
  reason for any extra term in a comment.

### 7. Experiments: sweeps and replications

- **Timing.** The first `run_grid` call on Windows or macOS fails if the run function is not
  in an importable file: show this in the walk-through, not in the exercises.
- **Misconceptions.** That seeds `0, 1, 2, ...` per run are as good as spawned seeds; that
  the result of a sweep depends on the number of workers (7.2: it does not); that a mean
  without its spread is a result.
- **Check.** That every table has the standard deviation or an interval next to the mean,
  and that the script reruns to the same table.

### 8. From the zoo to your own project

- **Timing.** No lecture: ten minutes on the project brief and the rubric below, then the
  pairs work on their own projects. Walk round and approve every group's question before
  1:00.
- **Misconceptions.** That the zoo's test can be dropped once the model is changed; that
  `MDL1xx` findings must all be fixed now.
- **Check.** Before the end: each group has a copied model, the zoo test passing in its
  folder, and one sentence stating its question.

### 9. Model cards and the hub

- **Timing.** If the room has no network, prepare the local index of exercise 9.4 before the
  session and set `MODELLY_HUB` on every machine.
- **Misconceptions.** That a card is documentation written once; that a stamped card means
  the model is right (9.3: a loose test stamps a changed model); that the out-of-scope list is
  a formality.
- **Check.** In 9.2, that no section is a paraphrase of the `TODO` and that the out-of-scope
  uses are specific to the model; in 9.3, that the student can say why the test passed.

### 10. Decisions: strategies and costs

- **Timing.** The study takes about five seconds per call; ask the pairs to keep the study
  of the walk-through in a notebook variable instead of rerunning it in every exercise.
- **Misconceptions.** That common random numbers always narrow the intervals (10.2: about 1
  on this model); that the cheapest strategy is the one that does least; that an ICER is a
  price to compare with zero; that the table recommends a policy (the card says the costs and
  fatality ratios are illustrative).
- **Check.** In 10.3, that the student connects the switch point to the ICER; in 10.4, that
  all strategies share one seed and that the cost function counts the doses.

### 11. Causes: effects, attribution and counterfactuals

- **Timing.** 11.1 runs 40 SEIR models (about five seconds); 11.2 and 11.3 are fast.
- **Misconceptions.** That an effect can be read from one run of each arm; that the person
  attribution ranks first "caused" the outbreak in a moral sense; that a counterfactual
  predicts what would happen in the real world.
- **Check.** In 11.1, the explanation of why the pairing fails here; in 11.3, the
  explanation of why the cure at step 10 changes nothing in the output chosen.

### 12. Continuous dynamics inside agents, and the projects

- **Timing.** One hour for the ODEs (lecture, walk-through, 12.1 and 12.2; 12.3 and 12.4 as
  homework), one hour for the presentations: ten minutes per group, five groups.
- **Misconceptions.** That one stacked `solve_ivp` call over all agents gives the same
  numbers as one call per agent (12.3); that event times are rounded to the step.
- **Check.** In 12.1, that the right-hand side is written for the whole population; in 12.2,
  that the error is relative and below the tolerance.

## Final project rubric

Each group presents in session 12 the project started in session 8 (see
[the list](session_12.md#final-project-presentations)). Mark it out of 20 from its folder,
which must run on a clean environment with `pip install modelly-abm` and the group's
instructions.

| Criterion | 0 | 2 | 4 |
|---|---|---|---|
| **Validation test** | none, or it does not run | runs, but compares with a value chosen to pass | compares with a known result or a limit case, tolerance derived from the variance or the solver's tolerance, zoo test kept |
| **Seeded experiment** | no script, or results by hand | a script, but the seed is missing or results change on rerun | a script that reruns to the same table, seeds spawned (`run_grid` or `compare`), replications per point |
| **Figure** | none | one run, or no axis labels and units | spread across seeds shown, labelled axes and units, the figure answers the question |
| **Model card** | none | present, with `TODO`s or generic text | `modelly card check` passes, out-of-scope uses and limits specific to the model |
| **Comparison with intervals** | means only | intervals, but unpaired or from one seed | paired on common random numbers, interval of the difference, `variance_reduction` or the paired interval reported and discussed |

Deduct 2 points, once, if `modelly lint` reports an `MDL0xx` finding: a reproducibility bug
undermines every other criterion. A group that states clearly what its model cannot answer
loses nothing for a negative result.

## Graded exercise A: a threshold with intervals

Set after session 7; one hour, individual, submitted as one script and a short paragraph.

> On a 60 x 60 forest, estimate the probability that the fire spans the raster at densities
> 0.55, 0.57, 0.59, 0.61, 0.63 and 0.65, with 20 seeds each and a 95% interval for each
> probability. Say between which densities the probability crosses one half, and compare
> with the site-percolation threshold `p_c = 0.5927`.

A reference solution:

```python
# spanning.py
import numpy as np

from modelly.batch import run_grid
from modelly.zoo.forest_fire.model import ForestFire, ForestScenario


def run(task):
    scenario = ForestScenario(
        rng=task["seed"], width=60, height=60, density=task["density"]
    )
    model = ForestFire(scenario)
    model.run()
    return {"spans": float(model.spans())}


if __name__ == "__main__":
    densities = [0.55, 0.57, 0.59, 0.61, 0.63, 0.65]
    frame = run_grid(run, {"density": densities}, replicates=20, seed=1)
    table = frame.groupby("density")["spans"].agg(["mean", "count"])
    table["half_width"] = 1.96 * np.sqrt(
        table["mean"] * (1 - table["mean"]) / table["count"]
    )
    print(table)
```

With `seed=1` the spanning share goes from 0 at 0.55 to 0.5 at 0.59 and 1 at 0.65.

**Marking (10 points).**

- 2: the run function is in an importable file with a `__main__` guard, and the seeds come
  from `run_grid` (or another `SeedSequence` spawn), not from `range(20)` by hand.
- 2: the script reruns to the same table.
- 2: an interval for each probability. Full marks for a Wilson or Clopper-Pearson interval,
  or for noting that the normal interval collapses to zero width at 0 and 1; 1 point for the
  normal interval without that remark.
- 2: the crossing is placed between two densities whose intervals are on either side of one
  half, not at a single density.
- 2: the comparison with `p_c`, and the remark that on a finite raster the transition is
  spread over a window that narrows as the raster grows (session 3).

## Graded exercise B: an effect and its card

Set after session 11; one hour, individual, submitted as one script, its output and three
card entries.

> In the Bass diffusion model, estimate the effect on adoption after 30 steps of raising
> `innovation` from 0.03 to 0.035 (more advertising), with 20 replicate pairs and seed 3.
> Report the effect with its interval and what common random numbers bought. Then write the
> `intended_use`, `out_of_scope` and `limits` entries of a model card for this use of the
> model.

A reference solution:

```python
from modelly.decide import model_runner
from modelly.explain import treatment_effect
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario

run = model_runner(
    BassDiffusion,
    {"adoption": lambda model: model.adoption},
    scenario=BassScenario,
    base={"steps": 30},
)
effect = treatment_effect(
    run, {}, {"innovation": 0.035}, "adoption", replicates=20, seed=3
)
print(effect.mean, effect.low, effect.high, effect.variance_reduction)
```

About 2.3 percentage points (2.1 to 2.5), with a variance about 14 times smaller than with
independent runs.

**Marking (10 points).**

- 2: `treatment_effect` (or `compare`) with the control and treated parameters right and
  the output read after 30 steps.
- 2: the effect reported with its interval and its units (a share of households, or
  percentage points), not as a bare number.
- 2: `variance_reduction` reported and explained: the same seed in both arms, and how many
  more runs independent seeds would need for the same interval.
- 2: the card entries are specific: `intended_use` names the comparison, `out_of_scope`
  rules out forecasting a real market's adoption without calibration, `limits` names at
  least one assumption of the model (homogeneous households, a fixed network or mixing).
- 2: the paragraph separates the model's chance, which the interval covers, from its
  assumptions, which it does not (the last section of [Decisions](../decide.md)).

## Teaching from NetLogo

Instructors moving a NetLogo course can start from the
[from NetLogo track](from_netlogo.md): how the concepts map, what the translator does, and
which sessions replace which usual lessons.
