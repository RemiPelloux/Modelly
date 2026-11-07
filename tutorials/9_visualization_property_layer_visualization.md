# Visualization - Property Layer Visualization

## The Boltzmann Wealth Model

If you want to get straight to the tutorial checkout these environment providers: 
 [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/RemiPelloux/Modelly/main?labpath=docs%2Ftutorials%2F9_visualization_property_layer_visualization.ipynb) (This can take 30 seconds to 5 minutes to load)

Due to conflict with Colab and Solara there are no colab links for this tutorial

*If you are running locally, please ensure you have the latest Modelly version installed.*

## Tutorial Description

This tutorial builds upon the [Visualization Rendering with SpaceRenderer](https://remipelloux.github.io/Modelly/tutorials/8_visualization_rendering_with_space_renderer.html) tutorial. We will explore more advanced features of the SpaceRenderer to create property_layer and their visualization.

*If you are starting here please see the [Running Your First Model tutorial](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html) for dependency and start-up instructions*

### Import Dependencies

This includes importing of dependencies needed for the tutorial.

```ipython3
# Has multi-dimensional arrays and matrices.
# Has a large collection of mathematical functions to operate on these arrays.
import numpy as np

# Data manipulation and analysis.
import pandas as pd

# Data visualization tools.
import seaborn as sns

import modelly
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.viz import SolaraViz, SpaceRenderer, make_plot_component
from modelly.viz.components import AgentPortrayalStyle, PropertyLayerStyle
```

## Basic Model

The following is the base model we’ll use to build the dashboard. It’s an extension of the model introduced in Tutorials 0–3, with an added property_layer called *Test* to demonstrate property_layer visualization functionalities.

```ipython3
def compute_gini(model):
    agent_wealths = [agent.wealth for agent in model.agents]
    x = sorted(agent_wealths)
    N = model.num_agents
    B = sum(xi * (N - i) for i, xi in enumerate(x)) / (N * sum(x))
    return 1 + (1 / N) - 2 * B

class MoneyAgent(CellAgent):
    """An agent with fixed initial wealth."""

    def __init__(self, model, cell):
        """initialize a MoneyAgent instance.

        Args:
            model: A model instance
        """
        super().__init__(model)
        self.cell = cell
        self.wealth = 1

    def move(self):
        """Move the agent to a random neighboring cell."""
        self.cell = self.cell.neighborhood.select_random_cell()

    def give_money(self):
        """Give 1 unit of wealth to a random agent in the same cell."""
        cellmates = [a for a in self.cell.agents if a is not self]

        if cellmates:  # Only give money if there are other agents present
            other = self.random.choice(cellmates)
            other.wealth += 1
            self.wealth -= 1

    def step(self):
        """do one step of the agent."""
        self.move()
        if self.wealth > 0:
            self.give_money()

class MoneyModel(modelly.Model):
    """A model with some number of agents."""

    def __init__(self, n=10, width=10, height=10, rng=None):
        """Initialize a MoneyModel instance.

        Args:
            N: The number of agents.
            width: Width of the grid.
            height: Height of the grid.
        """
        super().__init__(rng=rng)
        self.num_agents = n
        self.grid = OrthogonalMooreGrid((width, height), random=self.random)

        # Add a test property with random data
        self.grid.add_property_layer(
            "test", np.random.randint(0, 10, size=(width, height))
        )

        # Create agents
        MoneyAgent.create_agents(
            self,
            self.num_agents,
            self.random.choices(self.grid.all_cells.cells, k=self.num_agents),
        )

        self.datacollector = modelly.DataCollector(
            model_reporters={"Gini": compute_gini}, agent_reporters={"Wealth": "wealth"}
        )
        self.datacollector.collect(self)

    def step(self):
        """do one step of the model"""
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)
```

```ipython3
# Let's make sure the model works
model = MoneyModel(100, 10, 10)
model.run_for(20)

data = model.datacollector.get_agent_vars_dataframe()
# Use seaborn
g = sns.histplot(data["Wealth"], discrete=True)
g.set(title="Wealth distribution", xlabel="Wealth", ylabel="number of agents");
```

![../_images/dd3dcda53ce0ce14efb0ae5cb3004f0b027bef4f4d43a4bb6b6d3a818c251d7b.png](https://remipelloux.github.io/Modelly/_images/dd3dcda53ce0ce14efb0ae5cb3004f0b027bef4f4d43a4bb6b6d3a818c251d7b.png)

### Adding visualization

So far, we’ve built a model, run it, and analyzed some output afterwards. However, one of the advantages of agent-based models is that we can often watch them run step by step, potentially spotting unexpected patterns, behaviors or bugs, or developing new intuitions, hypotheses, or insights. Other times, watching a model run can explain it to an unfamiliar audience better than static explanations. Like many ABM frameworks, Modelly allows you to create an interactive visualization of the model. In this section we’ll walk through creating a visualization using built-in components, and (for advanced users) how to create a new visualization element.

First, a quick explanation of how Modelly’s interactive visualization works. The visualization is done in a browser window or Jupyter instance, using the [Solara](https://solara.dev/) framework, a pure Python, React-style web framework. Running `solara run app.py` will launch a web server, which runs the model, and displays model detail at each step via a plotting library. Alternatively, you can execute everything inside a Jupyter instance and display it inline.

As in the previous tutorial we instantiate the model parameters, some of which are modifiable by user inputs. In this case, the number of agents, N, is specified as a slider of integers.

```ipython3
model_params = {
    "n": {
        "type": "SliderInt",
        "value": 50,
        "label": "Number of agents:",
        "min": 10,
        "max": 100,
        "step": 1,
    },
    "width": 10,
    "height": 10,
}
```

Then just like last time we instantiate the visualization object which (by default) displays the grid containing the agents, and timeseries of values computed by the model’s data collector. In this example, we specify the Gini coefficient.

There are 3 buttons:

- the step button, which advances the model by 1 step
- the play button, which advances the model indefinitely until it is paused
- the pause button, which pauses the model

To reset the model, the order of operations are important

1. Stop the model
1. Update the parameters (e.g. move the sliders)
1. Press reset

**Additional Interactive Controls**

In addition to the basic controls (Play, Pause, Step), there are three extra interactive UI elements that give you more control over the simulation and visualization performance:

1. **Play Interval Slider** This slider controls the time delay (in milliseconds) between each step of the simulation when it is playing.
- **Lower values** = faster simulation updates
- **Higher values** = slower, more observable step-by-step updates
1. **Render Interval Slider** This slider determines how frequently the visualization updates, based on the number of steps.
- For example, if set to `5`, the visualization will update only **after every 5 steps** of the model.
- ⚠️ Note: This interval is **step-based**, not time-based.
1. **Use Threads Checkbox** This checkbox enables threaded execution of the model.
- When enabled, the visualization runs on a separate thread, allowing the UI to remain responsive even during heavy computations.
- It also ensures the visualization only updates at fixed intervals, improving performance and responsiveness during rapid simulations.

### Page Tab View

#### **Plot Components**

You can place different components (except the renderer) on separate pages according to your preference. There are no restrictions on page numbering — pages do not need to be sequential or positive. Each page acts as an independent window where components may or may not exist.

The default page is `page=0`. If pages are not sequential (e.g., `page=1` and `page=10`), the system will automatically create the 8 empty pages in between to maintain consistent indexing. To avoid empty pages in your dashboard, use sequential page numbers.

To assign a plot component to a specific page, pass the `page` keyword argument to `make_plot_component`. For example, the following will display the plot component on page 1:

```python
plot_comp = make_plot_component("encoding", page=1)
```

#### **Custom Components**

In the next tutorial, you will learn how to create custom components for the Solara dashboard. If you want a custom component to appear on a specific page, you must pass it as a tuple containing the component and the page number.

```python
@solara.component
def CustomComponent():
    ...

page = SolaraViz(
    model,
    renderer,
    components=[(CustomComponent, 1)]  # Custom component will appear on page 1
)
```

⚠️ **Warning** Running the model can be performance-intensive. It is strongly recommended to pause the model in the dashboard before switching pages.

## Visualizing property_layer

**⚠️ Important:** property_layer visualization on `HexGrid` is not supported with the `altair` backend; use `matplotlib` instead.

You can visualize **property_layer** in a way that’s very similar to how agents are visualized—by defining a custom portrayal function. Let’s call this function `property_layer_portrayal`.

Modelly provides a dedicated component for property_layer styling, called `PropertyLayerStyle` (similar to `AgentPortrayalStyle` for agents). You can import it from `modelly.viz.components` as shown earlier.

In `PropertyLayerStyle`, you can define:

- `color` or `colormap`: Determines how the values in the property_layer are visualized
- `alpha`: Controls the transparency (opacity) of the property_layer
- `colorbar`: A boolean that determines whether a colorbar is shown alongside the visualization
- `vmin` and `vmax`: The minimum and maximum data values to be visualized, controlling the color scale range, these default to the minimum and maximum values in your data respectively if not defined.

The portrayal function receives a `layer` object as an argument, just like how `agent_portrayal` receives an `agent`. If your model includes multiple property_layer, you can conditionally adjust the visualization logic based on the its name. This allows you to apply different styles to each property_layer as needed.

Here’s a quick example:

```python
def property_layer_portrayal(layer):
    if layer == "WealthDensity":
        return PropertyLayerStyle(
            colormap="viridis",
            alpha=0.6,
            colorbar=True,
            vmin=0,
            vmax=10,
        )
    elif layer == "Temperature":
        return PropertyLayerStyle(
            colormap="coolwarm",
            alpha=0.5,
            colorbar=False,
            vmin=-1,
            vmax=1,
        )
```

This approach allows you to customize each property_layer’s appearance independently while keeping your visualization code clean and modular.

We’ll reuse the previously defined `agent_portrayal` function and introduce a new `property_layer_portrayal` function specifically for visualizing the property_layer.

```ipython3
def agent_portrayal(agent):
    portrayal = AgentPortrayalStyle(size=50, color="orange")
    if agent.wealth > 0:
        portrayal.update(("color", "blue"), ("size", 100))
    return portrayal

def property_layer_portrayal(layer):
    if layer == "test":
        return PropertyLayerStyle(color="blue", alpha=0.8, colorbar=True)

# Create initial model instance
money_model = MoneyModel(n=50, width=10, height=10)
```

### Drawing the property_layer

We’ll now create a renderer and draw the grid structure, the agents and the *test* using the `matplotlib` backend.

```ipython3
%%capture

renderer = SpaceRenderer(model=money_model, backend="matplotlib")
renderer.draw_structure(lw=2, ls="solid", color="black", alpha=0.1)
renderer.draw_agents(agent_portrayal)
renderer.draw_property_layer(property_layer_portrayal)
```

You can also use `render()` function to draw property_layer in one go.

```ipython3
%%capture

renderer = SpaceRenderer(model=money_model, backend="matplotlib")
renderer.render(
    space_kwargs={  # an alternative way to customize the grid structure
        "lw": 2,
        "ls": "solid",
        "color": "black",
        "alpha": 0.1,
    },
    agent_portrayal=agent_portrayal,
    property_layer_portrayal=property_layer_portrayal,
)
```

We’ll keep the `post_process` to make the grid look good.

```ipython3
def post_process(ax):
    """Customize the matplotlib axes after rendering."""
    ax.set_title("Boltzmann Wealth Model")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_aspect("equal", adjustable="box")

renderer.post_process = post_process

def post_process_lines(ax):
    """Customize the matplotlib axes for the Gini line plot."""
    ax.set_title("Gini Coefficient Over Time")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Gini Coefficient")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_aspect("auto")

GiniPlot = make_plot_component("Gini", post_process=post_process_lines)
```

#### Launching the Visualization

Now that we have the model, visual renderer, and plot components defined, we can bring everything together using `SolaraViz`:

```ipython3
page = SolaraViz(
    money_model,
    renderer,
    components=[GiniPlot],
    model_params=model_params,
    name="Boltzmann Wealth Model",
)

# This is required to render the visualization in a Jupyter notebook
page
```

```myst-ansi
<Figure size 640x480 with 0 Axes>
```

## Exercise

- Try removing the `post_process` and changing the backend.
- Try visualizing multiple property_layers.

## Next Steps

Checkout this [modelly example](https://github.com/RemiPelloux/Modelly/tree/main/modelly/examples/advanced/sugarscape_g1mt) to further explore the capabilities of the property_layer. Check out the next [visualization tutorial custom components](https://remipelloux.github.io/Modelly/tutorials/10_visualization_custom.html) on how to further enhance your interactive dashboard.

[Comer2014] Comer, Kenneth W. “Who Goes First? An Examination of the Impact of Activation on Outcome Behavior in AgentBased Models.” George Mason University, 2014. http://mars.gmu.edu/bitstream/handle/1920/9070/Comer_gmu_0883E_10539.pdf

[Dragulescu2002] Drăgulescu, Adrian A., and Victor M. Yakovenko. “Statistical Mechanics of Money, Income, and Wealth: A Short Survey.” arXiv Preprint Cond-mat/0211175, 2002. http://arxiv.org/abs/cond-mat/0211175.
