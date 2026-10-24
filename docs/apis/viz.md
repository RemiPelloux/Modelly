# Viz

`modelly.viz` draws models in the browser and in notebooks. The names most models need are
exported by the package itself: `from modelly.viz import SolaraViz, SpaceRenderer`.

| Module | Contents |
|---|---|
| `modelly.viz.solara` | `SolaraViz`, the model controller, parameter inputs and `Slider` |
| `modelly.viz.components` | `make_space_component`, `make_plot_component` |
| `modelly.viz.render` | `SpaceRenderer`, the portrayal styles, backends and space drawers |
| `modelly.viz.mpl` | matplotlib backend, `draw_space` and plot components |
| `modelly.viz.altair` | Altair backend and plot components |
| `modelly.viz.console` | `CommandConsole` |

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


## Solara app

```{eval-rst}
.. automodule:: modelly.viz.solara.app
   :members: SolaraViz, JupyterViz, ModelController, ModelCreator, UserInputs, ShowSteps, ComponentsView, SpaceRendererComponent, create_space_component, copy_renderer, make_initial_grid_layout, split_model_params, check_param_is_fixed
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.components
   :members: make_space_component, make_plot_component
   :undoc-members:
   :show-inheritance:
```

## User parameters

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

## Command console

```{eval-rst}
.. automodule:: modelly.viz.console.console
   :members:
   :undoc-members:
   :show-inheritance:
```

## Portrayal components

```{eval-rst}
.. automodule:: modelly.viz.render.portrayal
   :members:
   :undoc-members:
   :show-inheritance:
```

## Backends

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

## Space renderer

```{eval-rst}
.. automodule:: modelly.viz.render.renderer
   :members:
   :undoc-members:
   :show-inheritance:
```

## Space drawers

```{eval-rst}
.. automodule:: modelly.viz.render.drawers.base
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.render.drawers.orthogonal
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.render.drawers.hexagonal
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.render.drawers.network
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.render.drawers.continuous
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.viz.render.drawers.voronoi
   :members:
   :undoc-members:
   :show-inheritance:
```
