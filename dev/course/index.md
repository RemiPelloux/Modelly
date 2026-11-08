# Course: agent-based modelling with Modelly

Twelve sessions that take a class from a first model to a validated, reproducible study of its own, with a model card and a comparison that a decision can rest on. Every session is built on a model of the [zoo](https://remipelloux.github.io/Modelly/dev/zoo/index.html), so the students start from code that is known to be right and spend their time on modelling questions. Each session lists its goals, what to read before, and exercises; the solutions are folded under each exercise. Sessions 9 to 12 also have a walk-through to run live.

Session

Topic

Zoo model

[1](https://remipelloux.github.io/Modelly/dev/course/session_1.html)

Agents, a scenario and a step

Boltzmann wealth exchange

[2](https://remipelloux.github.io/Modelly/dev/course/session_2.html)

Data, seeds and reproducibility

Boltzmann, Bouchaud-Mezard

[3](https://remipelloux.github.io/Modelly/dev/course/session_3.html)

Space: grids, rasters and percolation

Forest fire

[4](https://remipelloux.github.io/Modelly/dev/course/session_4.html)

Networks and contact structure

Bass diffusion, age-structured SEIR

[5](https://remipelloux.github.io/Modelly/dev/course/session_5.html)

Thinking in arrays: columns and cohorts

Nagel-Schreckenberg, SEIR

[6](https://remipelloux.github.io/Modelly/dev/course/session_6.html)

Validation against theory

SEIR, traffic, Bass

[7](https://remipelloux.github.io/Modelly/dev/course/session_7.html)

Experiments: sweeps and replications

Deffuant, Hegselmann-Krause, Axelrod

[8](https://remipelloux.github.io/Modelly/dev/course/session_8.html)

From the zoo to your own project

any

[9](https://remipelloux.github.io/Modelly/dev/course/session_9.html)

Model cards and the hub

Boltzmann, within-host epidemic

[10](https://remipelloux.github.io/Modelly/dev/course/session_10.html)

Decisions: strategies, common random numbers and costs

SEIR (vaccination study)

[11](https://remipelloux.github.io/Modelly/dev/course/session_11.html)

Causes: effects, attribution and counterfactuals

Bass diffusion, virus on a network

[12](https://remipelloux.github.io/Modelly/dev/course/session_12.html)

ODEs inside agents; the final presentations

within-host epidemic

## Running the course

- **Setup.** `pip install "modelly-abm[viz]"` and a Jupyter environment. The commands in the sessions are the same in bash and PowerShell unless a session shows both.
- **Format.** Each session is a lecture on the topic, a live walk through the zoo model, then the exercises in pairs. The [domain tutorials](https://remipelloux.github.io/Modelly/dev/tutorials/domains/index.html) are ready-made walk-throughs.
- **Assessment.** A small project, started in session 8 from a zoo model with `modelly zoo copy`, and presented in session 12 with its validation test, a seeded experiment, one figure, its model card and a comparison with intervals. Two short graded exercises, after sessions 7 and 11, check the same skills individually.
- **Instructor notes.** The [instructor notes](https://remipelloux.github.io/Modelly/dev/course/instructors.html) give the timing of each 2-hour session, the misconceptions students usually have, what to check in the exercises, the rubric of the final project and the graded exercises with their marking criteria.
- **Coming from NetLogo.** The [from NetLogo track](https://remipelloux.github.io/Modelly/dev/course/from_netlogo.html) maps NetLogo’s concepts to Modelly, shows what `modelly netlogo` translates and what is left to write, and says which sessions replace which usual NetLogo lessons.
