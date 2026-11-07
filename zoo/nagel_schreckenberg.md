# Nagel-Schreckenberg traffic

**Field:** transport · **Zoo name:** `nagel_schreckenberg` · **Module:** `modelly.zoo.nagel_schreckenberg.model`

![Fundamental diagram with and without dawdling](https://remipelloux.github.io/Modelly/_images/nagel_schreckenberg.png)

A single-lane ring road of `length` cells, each holding at most one car. Every step, all cars update in parallel: accelerate by one up to `max_speed`, brake to the number of empty cells ahead, slow down by one with probability `dawdle`, then move. Jams form spontaneously and travel backwards, against the traffic.

## How it is written

Cars are `Car` agents whose `position` and `velocity` are `Column` attributes. The whole road updates with a few numpy operations on `model.columns[Car]`: the gap to the car ahead is `roll(position, -1) - position - 1` modulo the road length, since cars never overtake and the rows therefore stay in road order. `fundamental_diagram(densities, transient, measured, ...)` measures the mean flow at each density.

```python
from modelly.zoo.nagel_schreckenberg.model import (
    NagelSchreckenberg,
    TrafficScenario,
    fundamental_diagram,
)

model = NagelSchreckenberg(TrafficScenario(rng=42))
model.run()
model.datacollector.get_model_vars_dataframe()  # flow and mean speed per step
fundamental_diagram([0.05, 0.1, 0.2, 0.4], 300, 200, rng=1)
```

Parameter

Default

Meaning

length

1000

cells of the ring road

density

0.15

share of cells holding a car

max_speed

5

speed limit, cells per step

dawdle

0.25

probability per step of slowing down by one at random

steps

500

run length of run()

## Validation

The fundamental diagram, flow (cars passing a point per step, `density * mean speed`) against density. `tests/zoo/test_nagel_schreckenberg.py` checks that:

- without dawdling, the steady flow is exactly `min(density * max_speed, 1 - density)` at seven densities on both sides of the critical density `1 / (max_speed + 1)`;
- with dawdling, the flow peaks at an interior density and falls steadily on the jammed branch;
- at low density every car runs at `max_speed - Bernoulli(dawdle)`, so the flow is `density * (max_speed - dawdle)` within five standard deviations of the mean of independent Bernoulli draws;
- cars never share a cell, impossible densities are rejected, and the same seed gives the same run.

## Model card: Nagel-Schreckenberg traffic

The Nagel-Schreckenberg cellular automaton: cars on a single-lane ring road accelerate, brake to the gap ahead and dawdle at random, and jams form on their own and travel backwards.

**Model:** `modelly.zoo.nagel_schreckenberg.model:NagelSchreckenberg` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `9105865a8431`

### Intended use

- Teaching the fundamental diagram of traffic: free flow below a critical density, jams above it, and how random dawdling lowers the peak flow.
- A starting point for cellular-automaton traffic models with a validated core to extend (lanes, on-ramps, signals).
- Comparing densities, speed limits or dawdling probabilities in relative terms.

### Out-of-scope use

- Predicting flows, speeds or travel times on a real road: cells, steps and dawdling are not calibrated to any road or driver population.
- Road design or safety decisions: there are no lanes, junctions, vehicle types or crashes.

### Data

- None by default: road length, density, speed limit and dawdling probability are illustrative values in `TrafficScenario`.

### Validation

Check

Test

without dawdling the steady flow is exactly min(density * max_speed, 1 - density) at seven densities on both sides of the critical density

tests/zoo/test_nagel_schreckenberg.py::test_deterministic_flow_is_exact

with dawdling the flow peaks at an interior density and falls steadily on the jammed branch

tests/zoo/test_nagel_schreckenberg.py::test_flow_rises_then_falls

at low density the flow is density * (max_speed - dawdle) within five standard deviations of the mean of independent Bernoulli dawdles

tests/zoo/test_nagel_schreckenberg.py::test_free_flow_speed_is_max_speed_minus_dawdle

cars never share a cell and never exceed the speed limit; impossible densities are rejected; same seed, same run

tests/zoo/test_nagel_schreckenberg.py

### Known limits

- One lane on a closed ring: no overtaking, entries, exits or junctions, and the number of cars is fixed.
- Space and time are discrete (one cell, one step) and every car follows the same rule with the same speed limit and dawdling probability.
- The exact checks hold away from the critical density `1 / (max_speed + 1)`, where transients are longest.

### Ethical considerations

- Results could be quoted in decisions about real roads that affect the people who use and live near them; present them as properties of an uncalibrated toy road, not as estimates for a real one.

## References

- Nagel, K. and Schreckenberg, M. (1992). A cellular automaton model for freeway traffic. *Journal de Physique I*, 2(12), 2221-2229.

Start a project from it with `modelly zoo copy nagel_schreckenberg my_traffic`.
