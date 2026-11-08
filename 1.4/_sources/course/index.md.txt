# Course: agent-based modelling with Modelly

Eight sessions that take a class from a first model to a validated, reproducible study of
its own. Every session is built on a model of the [zoo](../zoo/index.md), so the students
start from code that is known to be right and spend their time on modelling questions. Each
session lists its goals, what to read before, and exercises; the solutions are folded under
each exercise.

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

## Running the course

- **Setup.** `pip install "modelly-abm[viz]"` and a Jupyter environment. The commands in the
  sessions are the same in bash and PowerShell unless a session shows both.
- **Format.** Each session is a lecture on the topic, a live walk through the zoo model,
  then the exercises in pairs. The [domain tutorials](../tutorials/domains/index.md) are
  ready-made walk-throughs.
- **Assessment.** A small project, started in session 8 from a zoo model with
  `modelly zoo copy`, and presented with its validation test, a seeded experiment and one
  figure.

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
```
