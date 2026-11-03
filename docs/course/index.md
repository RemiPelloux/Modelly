# Course: agent-based modelling with Modelly

Twelve sessions that take a class from a first model to a validated, reproducible study of
its own, with a model card and a comparison that a decision can rest on. Every session is
built on a model of the [zoo](../zoo/index.md), so the students start from code that is known
to be right and spend their time on modelling questions. Each session lists its goals, what to read before, and exercises; the solutions are folded under
each exercise. Sessions 9 to 12 also have a walk-through to run live.

| Session | Topic | Zoo model |
|---|---|---|
| [1](session_1.md) | Agents, a scenario and a step | Boltzmann wealth exchange |
| [2](session_2.md) | Data, seeds and reproducibility | Boltzmann, Bouchaud-Mezard |
| [3](session_3.md) | Space: grids, rasters and percolation | Forest fire |
| [4](session_4.md) | Networks and contact structure | Bass diffusion, age-structured SEIR |
| [5](session_5.md) | Thinking in arrays: columns and cohorts | Nagel-Schreckenberg, SEIR |
| [6](session_6.md) | Validation against theory | SEIR, traffic, Bass |
| [7](session_7.md) | Experiments: sweeps and replications | Deffuant, Hegselmann-Krause, Axelrod |
| [8](session_8.md) | From the zoo to your own project | any |
| [9](session_9.md) | Model cards and the hub | Boltzmann, within-host epidemic |
| [10](session_10.md) | Decisions: strategies, common random numbers and costs | SEIR (vaccination study) |
| [11](session_11.md) | Causes: effects, attribution and counterfactuals | Bass diffusion, virus on a network |
| [12](session_12.md) | ODEs inside agents; the final presentations | within-host epidemic |

## Running the course

- **Setup.** `pip install "modelly-abm[viz]"` and a Jupyter environment. The commands in the
  sessions are the same in bash and PowerShell unless a session shows both.
- **Format.** Each session is a lecture on the topic, a live walk through the zoo model,
  then the exercises in pairs. The [domain tutorials](../tutorials/domains/index.md) are
  ready-made walk-throughs.
- **Assessment.** A small project, started in session 8 from a zoo model with
  `modelly zoo copy`, and presented in session 12 with its validation test, a seeded
  experiment, one figure, its model card and a comparison with intervals. Two short graded
  exercises, after sessions 7 and 11, check the same skills individually.
- **Instructor notes.** The [instructor notes](instructors.md) give the timing of each
  2-hour session, the misconceptions students usually have, what to check in the exercises,
  the rubric of the final project and the graded exercises with their marking criteria.
- **Coming from NetLogo.** The [from NetLogo track](from_netlogo.md) maps NetLogo's concepts
  to Modelly, shows what `modelly netlogo` translates and what is left to write, and says
  which sessions replace which usual NetLogo lessons.

```{toctree}
:hidden: true

session_1
session_2
session_3
session_4
session_5
session_6
session_7
session_8
session_9
session_10
session_11
session_12
instructors
from_netlogo
```
