# Modelly: agent-based modeling in Python

Agent-based models in Python, fast enough to explore.

Modelly is an open-source framework for agent-based modeling. Write agents with a `step()`, keep their state in numpy columns as the model grows, and get the same result from the same seed every time.

[Build your first model](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html)

## The same models, 2.9 to 135 times faster than Mesa 3.5

Nine playbooks written in the idiom of Mesa 3.5 and of Modelly: median CPU seconds over ten rounds, one fresh interpreter per run, on one pinned core. The scale is logarithmic.

Seconds per run, median of ten rounds

| Model | Size | Mesa 3.5 | Modelly | Speed-up |
|---|---|---|---|---|
| Grid epidemic | 20,000 agents, 60 steps | 3.99 s | 0.16 s | 26× |
| Predator-prey | ~5,400 agents, 200 steps | 3.67 s | 0.52 s | 7.1× |
| Flocking | 4,000 agents, 50 steps | 24.49 s | 0.75 s | 33× |
| Virus on a network | 30,000 agents, 100 steps | 2.52 s | 0.19 s | 13× |
| Insects, individuals | ~26,000 agents, 120 days | 2 s | 0.7 s | 2.9× |
| Insects, cohorts | ~26,000 agents, 120 days | 2 s | 0.015 s | 135× |
| Schelling segregation | ~32,000 residents, 40 steps | 3.57 s | 0.2 s | 18× |
| Boltzmann wealth | 10,000 agents, 100 steps | 1.14 s | 0.33 s | 3.5× |
| Sugarscape | 1,600 foragers, 100 steps | 1.44 s | 0.33 s | 4.4× |

**Same answers** Every variant runs the same seeds. Over 100 paired seeds, no summary statistic differs from Mesa's after a Holm correction.

**Same seed, same run** Each implementation runs its first seed twice and must reproduce it exactly.

**Re-run it yourself** The playbooks and the runner are in [benchmarks/playbooks](https://github.com/RemiPelloux/Modelly/tree/main/benchmarks/playbooks); the method, the other baselines (Mesa 2.3, mesa-frames, hand-vectorised Mesa) and the variance are on the [performance page](https://remipelloux.github.io/Modelly/performance.html).

## What people model with it

Each sketch below is a small version of a playbook or a shipped example, running in your browser.

### Epidemics on a grid

Susceptible, infected and recovered agents on a 20,000-cell torus. Exposure is one count over the grid's adjacency, so 60 steps take 0.32 s, building included.

[Read the playbook](https://remipelloux.github.io/Modelly/performance.html)
