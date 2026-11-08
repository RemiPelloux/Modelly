# Session 3: space, rasters and percolation

**Zoo model:** [Forest fire](../zoo/forest_fire.md)

## Goals

- Put a model on a grid, and number its cells with a `CellIndex` so that a whole-landscape
  question ("which trees touch a fire?") is one sparse product.
- Read a per-cell state as a raster (`index.to_layer`) and plot it.
- Meet a phase transition: the percolation threshold.

**Before the session:** the [adding space](../tutorials/4_adding_space.ipynb) tutorial and
[Vectorised step phases](../vectorised_phases.md), section 2.

## Exercises

**3.1** Run the forest fire at densities 0.5, 0.6 and 0.7 on a 100 x 100 raster. For each,
print the burnt share and whether the fire reached the east edge.

<details>
<summary>Solution</summary>

```python
from modelly.zoo.forest_fire.model import ForestFire, ForestScenario

for density in (0.5, 0.6, 0.7):
    model = ForestFire(ForestScenario(rng=1, density=density))
    model.run()
    print(density, round(model.burnt_share(), 2), model.spans())
```

At 0.5 the fire dies near the west edge; at 0.7 it crosses. 0.6 is close to the threshold
`p_c = 0.5927`, where the outcome depends on the seed.

</details>

**3.2** Estimate the probability that the fire spans the raster at density 0.59, from twenty
seeds, on rasters of side 30 and 120. What happens to the transition as the raster grows?

<details>
<summary>Solution</summary>

```python
import numpy as np

for side in (30, 120):
    spans = []
    for seed in range(20):
        model = ForestFire(
            ForestScenario(rng=seed, width=side, height=side, density=0.59)
        )
        model.run()
        spans.append(model.spans())
    print(side, np.mean(spans))
```

Near `p_c` the spanning probability is neither 0 nor 1; the window of densities where it
is uncertain narrows as the raster grows (as `L^(-3/4)` for two-dimensional percolation),
so on an infinite landscape the transition is sharp.

</details>

**3.3** In `ForestFire.step`, which line finds the trees next to a fire? Explain why it is one
sparse matrix-vector product and not a loop over trees.

<details>
<summary>Solution</summary>

`exposed = self.index.neighbor_sum(burning.astype(np.int32)) > 0`. `CellIndex` builds the
adjacency matrix of the grid once; multiplying it by the vector "is burning" gives, for every
cell, the number of burning neighbours.

</details>

**3.4** Make a landscape with a firebreak: no trees in a vertical strip in the middle. Pass it
as `cover` and check that the fire stops at the strip even at density 0.8.

<details>
<summary>Solution</summary>

```python
side = 100
cover = np.full((side, side), 0.8)  # indexed [x, y]
cover[48:52, :] = 0.0
model = ForestFire(ForestScenario(rng=1, density=0.8, cover=cover))
model.run()
print(model.spans())  # False
```

A land-cover raster read with `modelly.space.geo.RasterLayer` has the same `[x, y]` layout in
its `values`.

</details>
