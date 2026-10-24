# Visualization


⚠️ **Important note for SolaraViz users**

When using **SolaraViz**, Modelly models must be instantiated **using keyword arguments only**.
SolaraViz creates model instances internally via keyword-based parameters, and positional arguments are **not supported**.

**Not supported:**

```python
MyModel(10, 10)
```

**Supported:**

```python
MyModel(width=10, height=10)
```

To avoid errors, it is recommended to define your model constructor with keyword-only arguments, for example:

```python
class MyModel(Model):
    def __init__(self, *, width, height, rng=None): ...
```


For detailed tutorials, please refer to:

- [Basic Visualization](../tutorials/6_visualization_basic)
- [Dynamic Agent Visualization](../tutorials/7_visualization_dynamic_agents)
- [Custom Visualization Components](../tutorials/10_visualization_custom)


## Jupyter Visualization

```{eval-rst}
.. automodule:: modelly.viz.solara.app
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.components.__init__
   :members:
   :undoc-members:
   :show-inheritance:
```

## User Parameters

```{eval-rst}
.. automodule:: modelly.viz.solara.params
   :members:
   :undoc-members:
   :show-inheritance:
```


## Matplotlib-based visualizations

```{eval-rst}
.. automodule:: modelly.viz.mpl.components
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.mpl.space
   :members:
   :undoc-members:
   :show-inheritance:
```


## Altair-based visualizations

```{eval-rst}
.. automodule:: modelly.viz.altair.components
   :members:
   :undoc-members:
   :show-inheritance:
```


## Command Console

```{eval-rst}
.. automodule:: modelly.viz.console.console
   :members:
   :undoc-members:
   :show-inheritance:
```


## Portrayal Components
```{eval-rst}
.. automodule:: modelly.viz.render.portrayal
   :members:
   :undoc-members:
   :show-inheritance:
```


## Backends

```{eval-rst}
.. automodule:: modelly.viz.render.__init__
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.render.backend
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.altair.backend
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.mpl.backend
   :members:
   :undoc-members:
   :show-inheritance:
```


## Space Renderer

```{eval-rst}
.. automodule:: modelly.viz.render.renderer
   :members:
   :undoc-members:
   :show-inheritance:
```


## Space Drawers

```{eval-rst}
.. automodule:: modelly.viz.render.drawers
   :members:
   :undoc-members:
   :show-inheritance:
```
