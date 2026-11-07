# Decisions

`modelly.decide` turns model runs into a comparison that a decision can rest on. It compares
strategies with intervals, costs them against what they achieve, tests them across many
possible futures, and searches a policy's parameters. Every result comes from a seed, so the
same study rerun gives the same tables.

```python
from modelly.decide import Strategy, compare, cost_effectiveness, model_runner

run = model_runner(AgeSEIR, {"deaths": deaths}, scenario=SEIRScenario)
study = compare(
    run,
    [Strategy("nobody"), Strategy("seniors", {"vaccinated": (0, 0, 10_000)})],
    replicates=20,
    seed=7,
)
study.rank("deaths")  # best first, with intervals and how often each was best
study.difference("deaths")  # each strategy minus the first, paired by replicate
```

## Comparing strategies

A `Strategy` is a name, the parameters it sets and its cost: a number, or a function of one
run's outputs. `compare(run, strategies, replicates=..., seed=...)` runs each strategy
`replicates` times. `run(params, seed)` builds and runs the model and returns its outputs;
`model_runner(model_class, outputs, scenario=...)` writes that function for you.

Replicate `r` of every strategy gets the same seed: **common random numbers**. When the
strategies consume the random numbers the same way, they face the same chance events (the
same first infections, the same unlucky contacts), the difference between two strategies in
one replicate is close to the effect of the strategy alone, and `difference(output)`, the
interval of those paired differences, is much narrower than the two separate intervals. When
a strategy changes the order of the draws, the pairing buys little: measure it with
`modelly.explain.treatment_effect`, which reports the variance reduction (see
[Causes and explanations](explain.md#treatment-effects-and-common-random-numbers)). `summary(output)` gives each
strategy's mean and Student-t interval (95% by default, `confidence=` to change it).
`rank(output, lower_is_better=True)` orders the strategies and adds `best_share`: the share of
replicates in which each was the best, an estimate of the probability that it is the right
choice.

The runs are independent, so `workers=` spreads them over processes: `compare`, `robust` and
`optimise` take it (default 1, one run after another; `None` uses every core). The results
come back in the order the loop gives, with the same seeds, so they are identical whatever
`workers` is. `run` is sent to each worker; a closure such as `model_runner`'s needs Linux,
where workers are forked. `optimise` runs one trial's replicates in parallel and its trials
in turn, since each trial depends on the ones before.

## A worked example: who gets the vaccine?

`modelly.decide.vaccination` is the study of this section. In the
[age-structured SEIR model](zoo/age_seir.md) (100,000 people in three age groups), 10,000
doses can be given before the epidemic to children, to adults, to seniors, or to nobody. The
outputs are the infections and the deaths, each group's infections times an illustrative
fatality ratio (0.01%, 0.2%, 3%). The cost is 20 per dose plus 150 per infection for care.

```python
from modelly.decide import cost_effectiveness, net_benefit
from modelly.decide.vaccination import vaccination_study

study = vaccination_study(replicates=20, seed=7)
study.rank("deaths")
cost_effectiveness(study, "deaths_averted")
net_benefit(study, "deaths_averted", wtp=100_000)
```

| Strategy | Deaths (95% interval) | Deaths averted vs nobody | Cost | Status | Cost per death averted |
|---|---|---|---|---|---|
| seniors | 242.0 (241.0 to 243.1) | 180.0 (178.3 to 181.8) | 10.76 M | frontier | 9,942 over children |
| adults | 359.1 (357.9 to 360.4) | 62.9 (61.5 to 64.3) | 9.75 M | extendedly dominated | |
| children | 370.0 (368.0 to 372.1) | 52.0 (49.9 to 54.1) | 9.49 M | frontier (cheapest) | |
| nobody | 422.1 (420.7 to 423.4) | 0 | 11.61 M | dominated | |

Vaccinating the children is the cheapest choice, cheaper than giving no doses at all,
because children drive transmission and every infection they would have passed on costs
care. Vaccinating the seniors averts the most deaths, at 9,942 per extra death averted over
vaccinating the children. Seniors were the best choice in every replicate (`best_share` 1.0),
and the intervals of the deaths averted are under four deaths wide. Here the pairing is not
what makes them narrow: vaccinating adds a cohort row, which reorders the draws, so the arms
are close to independent (variance ratio about 0.8); 100,000 people make each run's result
precise on its own. Run again with the same seed, the study gives
the same tables (`tests/decide/test_decide.py`). The fatality ratios and costs are
illustrative: the model's card, at the end of [its page](zoo/age_seir.md), says what it must
not be used for.

## Cost-effectiveness

`cost_effectiveness(comparison, effect)` places the strategies by mean cost and mean effect.
A strategy is **dominated** when another costs no more and achieves at least as much, and
**extendedly dominated** when a mix of two others would buy more effect for the same money.
The remaining strategies form the efficient frontier. Each has an incremental
cost-effectiveness ratio (`icer`) over the previous one: the price of one more unit of
effect. `net_benefit(comparison, effect, wtp)` sets a willingness to pay per unit of effect
and ranks `wtp * effect - cost` per replicate, with intervals.

## Robust decisions

When the world's parameters are uncertain, a strategy tuned to one best guess can fail
elsewhere. `robust` runs every strategy in every future:

```python
from modelly.decide import robust, sample_futures

futures = sample_futures({"beta": (0.025, 0.05), "recovery": (0.15, 0.3)}, 30, seed=1)
result = robust(run, strategies, futures, "deaths", replicates=5, threshold=300)
result.summary()  # mean, worst, max_regret, mean_regret, satisficing; minimax regret first
```

`sample_futures` draws futures by Latin hypercube sampling from ranges. Within a future every
strategy gets the same seeds. The **regret** of a strategy in a future is how much worse it
does than the best strategy there. `summary()` ranks by the largest regret (minimax regret),
the usual criterion when the futures cannot be given probabilities. With a `threshold` it
also reports the share of futures in which each strategy meets it.

## Optimising an intervention

`optimise(run, space, objective, trials=50, seed=0)` searches a policy's parameters with
Optuna's TPE sampler (`pip install "modelly-abm[decide]"`). `space` maps names to ranges or
lists of choices. Every proposal is evaluated on the same replicate seeds, and the sampler is
seeded, so the same call gives the same trials and the same optimum:

```python
from modelly.decide import optimise

best = optimise(
    run,
    {"vaccinated_seniors": (0, 20_000)},
    lambda out: out["deaths"],
    trials=40,
    seed=2,
)
best.params, best.value, best.trials
```

## What these numbers are not

A comparison is only as good as its model: intervals cover the model's chance, not its
assumptions. Read the [model card](model_cards.md) before presenting a ranking, show the
intervals with it, and say what was left out. The tables above never forecast what will
happen; they say which strategy does best in the model, and by how much.
