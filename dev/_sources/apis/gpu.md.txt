# GPU

`modelly.gpu` runs column phases, cohort tables and cell-space operators on numpy, CuPy or JAX,
with counter-based random numbers that are the same on every backend. How to use it is in
[GPU arrays](../gpu.md).

## Backends

```{eval-rst}
.. automodule:: modelly.gpu.backend
   :members:
```

```{eval-rst}
.. automodule:: modelly.gpu.cupy_backend
   :members:
```

```{eval-rst}
.. automodule:: modelly.gpu.jax_backend
   :members:
```

## Random streams

```{eval-rst}
.. automodule:: modelly.gpu.philox
   :members:
```

```{eval-rst}
.. automodule:: modelly.gpu.streams
   :members:
```

```{eval-rst}
.. automodule:: modelly.gpu.binomial
   :members: binomial
```

## Tables and cell spaces

```{eval-rst}
.. automodule:: modelly.gpu.table
   :members:
```

```{eval-rst}
.. automodule:: modelly.gpu.cohorts
   :members:
```

```{eval-rst}
.. automodule:: modelly.gpu.cells
   :members:
```

## Memory

```{eval-rst}
.. automodule:: modelly.gpu.memory
   :members:
```
