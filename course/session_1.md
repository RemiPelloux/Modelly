# Session 1: agents, a scenario and a step

**Zoo model:** [Boltzmann wealth exchange](https://remipelloux.github.io/Modelly/zoo/kinetic_wealth.html)

## Goals

- Know the three pieces of a Modelly model: a `Scenario` (the inputs), agents, and a `Model` with a `step`.
- Run a model, read its state, and change a parameter without editing the code.
- See an emergent result: identical agents trading at random end up unequal.

**Before the session:** [Getting started](https://remipelloux.github.io/Modelly/getting_started.html) and the first tutorial, [your first model](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html).

## Exercises

**1.1** Run `KineticWealth` with its default scenario and print the richest agent’s wealth and the share of agents with no money at all.

Solution

```python
from modelly.zoo.kinetic_wealth.model import KineticScenario, KineticWealth

model = KineticWealth(KineticScenario(rng=1))
model.run()
print(model.wealth.max(), (model.wealth == 0).mean())
```

About a sixth of the agents end with nothing (the stationary law puts probability close to `1 / (money + 1)` on zero) and the richest hold several times the mean.

**1.2** Every agent starts with `money` units. Double it. Does the Gini coefficient change? Why?

Solution

```python
for money in (5, 10):
    model = KineticWealth(KineticScenario(rng=1, money=money))
    model.run()
    print(money, model.datacollector.get_model_vars_dataframe().iloc[-1, 0])
```

Barely: the stationary law is close to the exponential distribution, whose Gini is 1/2 whatever its mean. With few units per agent the integer law is a little more unequal.

**1.3** Read `KineticWealth.step` in `modelly/zoo/kinetic_wealth/model.py`. Write, in one sentence each, what the four lines between `order = ...` and `taker = ...` do.

Solution

A random permutation of the agents; its two halves are paired element by element; a coin per pair; the coin picks which member of each pair gives and which takes. Every agent trades exactly once per step.

**1.4** Change the rule so that a giver passes two units when it has at least two. Copy the model first: `modelly zoo copy kinetic_wealth my_wealth`.

Solution

In `my_wealth/model.py`, in `step`, replace the transfer with:

```python
amount = np.minimum(wealth[giver], 2)
wealth[giver] -= amount
wealth[taker] += amount
```

`wealth[taker] += amount` is safe because every agent appears once in the matching, so no index repeats.
