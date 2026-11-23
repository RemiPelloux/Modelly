# Bass diffusion of innovation on a network

**Field:** energy · **Zoo name:** `bass_diffusion` · **Module:** `modelly.zoo.bass_diffusion.model`

![Adoption curves against the Bass equation](https://remipelloux.github.io/Modelly/_images/bass_diffusion.png)

Households adopt an innovation, rooftop solar panels for instance. In each step of length `dt` years a household that has not adopted does so with probability `(innovation + imitation * share) * dt`, where `innovation` (Bass’s `p`) is the pull of advertising and `imitation` (Bass’s `q`) the pull of the households it knows. `share` is the share of adopters among everybody (`mixing="well-mixed"`, Bass’s original model) or among the household’s neighbours in a random network of mean degree `degree` (`mixing="network"`).

## How it is written

Households are `Household` agents with an `adopted` `Column`; a step is one `ColumnTable.draw` for the whole population. The network is a one-layer `MultilayerNetwork` (see [Networks](https://remipelloux.github.io/Modelly/networks.html)), so the share of adopting neighbours of every household is one sparse product, `adjacency() @ adopted`, divided by the degrees.

```python
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario, bass_curve

model = BassDiffusion(BassScenario(rng=42, mixing="network", degree=8))
model.run()
frame = model.datacollector.get_model_vars_dataframe()  # time (years), adoption share
bass_curve(frame["time"], 0.03, 0.38)  # the well-mixed Bass solution
```

Parameter

Default

Meaning

households

5000

number of households

innovation

0.03

Bass p, adoption rate per year from outside influence

imitation

0.38

Bass q, adoption rate per year when every neighbour has adopted

dt

0.1

step length, years

mixing

"well-mixed"

"well-mixed" or "network"

degree

10.0

mean number of neighbours in the random network

steps

200

run length of run()

## Validation

In the well-mixed limit the expected adoption share follows the Bass equation `dF/dt = (p + q F)(1 - F)`, solved by `F(t) = (1 - exp(-(p + q) t)) / (1 + (q / p) exp(-(p + q) t))` (`bass_curve`). `tests/zoo/test_bass_diffusion.py` checks, with three seeds, that the simulated share is within the Euler discretisation error (the step recursion against the exact solution) plus five standard deviations of the ODE at every step. The standard deviation comes from the linear noise approximation: each step adds binomial noise of variance `(1 - F) h (1 - h) / N`, with `h = (p + q F) dt`, and a deviation grows by `1 + f'(F)` per step. It also checks that a dense network (50 neighbours) stays within the same bound, that a sparse one (4 neighbours) lags the well-mixed curve at mid-diffusion, because non-adopters cluster together, and that the same seed gives the same curve.

## Model card: Bass diffusion of innovation on a network

Households adopt an innovation, rooftop solar for instance, from advertising and from adopting neighbours, either well mixed as in Bass’s model or over a random network.

**Model:** `modelly.zoo.bass_diffusion.model:BassDiffusion` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `fb359feb19e8`

### Intended use

- Teaching the Bass diffusion curve and the roles of innovation (p) and imitation (q).
- Showing how network structure changes diffusion: a sparse network adopts more slowly than the well-mixed curve.
- A starting point for adoption models (solar, heat pumps) with a validated core to extend (subsidies, heterogeneous households, real networks).

### Out-of-scope use

- Forecasting real adoption of a product or technology: the default p and q are illustrative, not fitted to sales or installation data.
- Decisions about subsidies or targeting real households without parameters and a network estimated on them.
- Products that can be abandoned or bought repeatedly: adoption here is once and for ever.

### Data

- None by default: the number of households, p, q, the step and the mean degree are illustrative values in `BassScenario`.
- The network, when used, is a random graph drawn by the model (`households * degree / 2` random distinct pairs), not a measured social network.

### Validation

Check

Test

well mixed, for three seeds, the adoption share is within the Euler error plus five linear-noise standard deviations of the Bass equation at every step

tests/zoo/test_bass_diffusion.py::test_well_mixed_follows_bass_equation

a dense network (50 neighbours) stays within the same bound

tests/zoo/test_bass_diffusion.py::test_dense_network_is_close_to_well_mixed

a sparse network (4 neighbours) lags the well-mixed recursion by more than three standard deviations at mid-diffusion

tests/zoo/test_bass_diffusion.py::test_sparse_network_adopts_more_slowly

adoption never reverts; unknown mixing is rejected; same seed, same curve

tests/zoo/test_bass_diffusion.py

### Known limits

- Every household has the same p and q; there are no prices, incomes, dwelling types or capacity limits.
- Adoption is drawn once per step of length `dt`, so the curve carries an Euler discretisation error against the Bass equation.
- The network is Erdos-Renyi-like with no clustering or communities beyond chance; real acquaintance networks are not represented.
- Closed population: no new households and no abandonment.

### Ethical considerations

- Results on who adopts first could inform which households a programme targets; present them with the assumptions above, since the model knows nothing about who can afford an innovation.

## References

- Bass, F. M. (1969). A new product growth for model consumer durables. *Management Science*, 15(5), 215-227.

Start a project from it with `modelly zoo copy bass_diffusion my_diffusion`.
