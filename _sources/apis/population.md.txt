# Synthetic populations

`modelly.population` builds people, households, places and contact networks from aggregate
tables. It needs numpy and pandas; `locate_households` takes a `GeoSpace` (the `geo` extra).
The guide is [Synthetic populations](../population.md).

| Module | Contents |
|---|---|
| `modelly.population.fitting` | `ipf`, `trs`, `synthesize_population`, `marginal_errors` |
| `modelly.population.annealing` | `anneal`, `Annealing`, `total_absolute_error` |
| `modelly.population.households` | `assign_households`, `household_sizes`, `HouseholdSpec` |
| `modelly.population.places` | `locate_households`, `assign_places`, `PlaceSpec` |
| `modelly.population.contacts` | `contact_network`, `place_groups`, `ContactLayers` |

## Fitting marginals

```{eval-rst}
.. automodule:: modelly.population.fitting
   :members:
```

## Combinatorial optimisation

```{eval-rst}
.. automodule:: modelly.population.annealing
   :members:
```

## Households

```{eval-rst}
.. automodule:: modelly.population.households
   :members:
```

## Homes and places

```{eval-rst}
.. automodule:: modelly.population.places
   :members:
```

## Contact networks

```{eval-rst}
.. automodule:: modelly.population.contacts
   :members:
```
