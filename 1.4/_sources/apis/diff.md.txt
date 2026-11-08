# Differentiable models

`modelly.diff` simulates models written as JAX phases and differentiates their outputs with
respect to their parameters. How to use it, and when the gradients mean something, is in
[Differentiable models](../differentiable.md).

## Models and phases

```{eval-rst}
.. automodule:: modelly.diff.model
   :members:
```

## Discrete choices

```{eval-rst}
.. automodule:: modelly.diff.estimators
   :members:
```

## Gradient checks

```{eval-rst}
.. automodule:: modelly.diff.check
   :members:
```

## Gradient-based calibration

```{eval-rst}
.. automodule:: modelly.diff.calibrate
   :members:
```

## Zoo twins

```{eval-rst}
.. automodule:: modelly.zoo.bouchaud_mezard.differentiable
   :members:
```

```{eval-rst}
.. automodule:: modelly.zoo.bass_diffusion.differentiable
   :members:
```
