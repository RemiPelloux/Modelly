# Visualization - Advanced Space Rendering

## The Boltzmann Wealth Model

If you want to get straight to the tutorial checkout these environment providers: 
 [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/RemiPelloux/Modelly/main?labpath=docs%2Ftutorials%2F8_visualization_rendering_with_space_renderer.ipynb) (This can take 30 seconds to 5 minutes to load)

Due to conflict with Colab and Solara there are no colab links for this tutorial

*If you are running locally, please ensure you have the latest Modelly version installed.*

## Tutorial Description

This tutorial builds upon the [Dynamic Agent Representation](https://remipelloux.github.io/Modelly/tutorials/7_visualization_dynamic_agents.html) tutorial. We will explore more advanced features of the SpaceRenderer to create more informative and visually appealing spatial visualizations.

Specifically, we’ll learn how to style the grid lines.

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
from modelly.viz.components import AgentPortrayalStyle
```

## Basic Model

The following is the basic model we will be using to build the dashboard. This is the same model seen in tutorials 0-3.

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
            width: width of the grid.
            height: Height of the grid.
        """
        super().__init__(rng=rng)
        self.num_agents = n
        self.grid = OrthogonalMooreGrid((width, height), random=self.random)

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
# Lets make sure the model works
model = MoneyModel(100, 10, 10)
model.run_for(20)

data = model.datacollector.get_agent_vars_dataframe()
# Use seaborn
g = sns.histplot(data["Wealth"], discrete=True)
g.set(title="Wealth distribution", xlabel="Wealth", ylabel="number of agents");
```

![../_images/56065fa0a71452e724322afd6de51ee0d5dfae61539c1096a0b1ff9c3766fd12.png](https://remipelloux.github.io/Modelly/_images/56065fa0a71452e724322afd6de51ee0d5dfae61539c1096a0b1ff9c3766fd12.png)

### Adding visualization

So far, we’ve built a model, run it, and analyzed some output afterwards. However, one of the advantages of agent-based models is that we can often watch them run step by step, potentially spotting unexpected patterns, behaviors or bugs, or developing new intuitions, hypotheses, or insights. Other times, watching a model run can explain it to an unfamiliar audience better than static explanations. Like many ABM frameworks, Modelly allows you to create an interactive visualization of the model. In this section we’ll walk through creating a visualization using built-in components, and (for advanced users) how to create a new visualization element.

First, a quick explanation of how Modelly’s interactive visualization works. The visualization is done in a browser window or Jupyter instance, using the [Solara](https://solara.dev/) framework, a pure Python, React-style web framework. Running `solara run app.py` will launch a web server, which runs the model, and displays model detail at each step via a plotting library. Alternatively, you can execute everything inside a Jupyter instance and display it inline.

As like last time we then instantiate the model parameters, some of which are modifiable by user inputs. In this case, the number of agents, N, is specified as a slider of integers.

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

In tutorial 8, you will learn how to create custom components for the Solara dashboard. If you want a custom component to appear on a specific page, you must pass it as a tuple containing the component and the page number.

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

## Advanced Rendering with `SpaceRenderer`

**⚠️ Important:** Modelly supports both `matplotlib` and `altair` backends for rendering, but **they are not interchangeable** when it comes to visualization methods and `post_process` functions.

- `matplotlib`-specific functions like `ax.set_title()` will not work with `altair`, and vice versa.
- **Be sure to run only the code blocks corresponding to the backend you are using**.
- Mixing backend-specific calls will lead to runtime errors.

`SpaceRenderer` is a powerful tool in Modelly for visualizing spatial grids. It goes beyond simply drawing agents — it allows detailed customization of the grid, dynamic styling of agents, and the ability to overlay calculated values as *property layers*. Property layers effectively act as heatmaps, coloring each grid cell based on model-defined data (more on this in the next tutorial).

In this section, we’ll demonstrate:

- Styling the grid using `setup_structure()`
- Customizing agent appearance with `setup_agents()`
- Enhancing the final visualization using the `post_process` function
- Applying these techniques to both `matplotlib` and `altair` backends

Before we begin, we’ll reuse the `agent_portrayal` function and `money_model` defined in the previous tutorial.

```ipython3
def agent_portrayal(agent):
    portrayal = AgentPortrayalStyle(size=50, color="orange")
    if agent.wealth > 0:
        portrayal.update(("color", "blue"), ("size", 100))
    return portrayal

# Create initial model instance
money_model = MoneyModel(n=50, width=10, height=10)
```

### Drawing the Grid and Agents

We’ll now create a renderer and draw both the grid structure and the agents using the `matplotlib` backend.

```ipython3
%%capture

renderer = SpaceRenderer(model=money_model, backend="matplotlib")
renderer.setup_structure(lw=2, ls="solid", color="black", alpha=0.1)
renderer.setup_agents(agent_portrayal)
renderer.render()
```

You can pass drawing keyword arguments (kwargs) directly to setup_structure() to customize the grid appearance. See the full list of accepted arguments in the [SpaceDrawer documentation](https://remipelloux.github.io/Modelly/apis/viz.html#space-drawers).

#### Using Altair Backend

The same can be achieved with the `altair` backend:

```ipython3
%%capture

renderer = SpaceRenderer(model=money_model, backend="altair")
renderer.setup_structure(
    xlabel="x",
    ylabel="y",
    grid_width=2,
    grid_dash=[1],
    grid_color="black",
    grid_opacity=0.1,
    title="Boltzmann Wealth Model",
)
renderer.setup_agents(agent_portrayal)
renderer.render()
```

##### Customizing the Final Output with `post_process`

You can use a post_process function to make high-level visual tweaks after the rendering is complete. This is especially useful for setting axis labels, titles, aspect ratios, and more.

The post_process can be passed into either the render() function or set differently as a property of SpaceRenderer.

**With `matplotlib`:**

```ipython3
def post_process(ax):
    """Customize the matplotlib axes after rendering."""
    ax.set_title("Boltzmann Wealth Model")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_aspect("equal", adjustable="box")

renderer.post_process = post_process
```

**With `Altair`:**

```ipython3
def post_process(chart):
    """Customize the Altair chart after rendering."""
    chart = (
        chart.properties(
            title="Boltzmann Wealth Model",
            width=600,
            height=400,
        )
        .configure_axis(
            labelFontSize=12,
            titleFontSize=14,
        )
        .configure_title(fontSize=16)
    )
    return chart

renderer.post_process = post_process
```

You can also use `post_process` with plots or other components.

##### Post-Processing Line Plots

**NOTE**: The backend of plot components can be the same as, or different from, that of the SpaceRenderer, depending on your preference.

Let’s apply `post_process` to a line chart of the Gini coefficient over time:

```ipython3
def post_process_lines(ax):
    """Customize the matplotlib axes for the Gini line plot."""
    ax.set_title("Gini Coefficient Over Time")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Gini Coefficient")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_aspect("auto")

GiniPlot = make_plot_component("Gini", post_process=post_process_lines)
```

##### Launching the Full Visualization

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

## Exercise

- Try different agent shapes, colors, and grid styles.
- Experiment with post_process to improve the look and feel of the final output.
- Add additional time-series plots.

## Next Steps

Checkout [modelly examples](https://github.com/RemiPelloux/Modelly/tree/main/modelly/examples) to further explore the capabilities of the visualization stack. Check out the next [property layer visualization](https://remipelloux.github.io/Modelly/tutorials/9_visualization_property_layer_visualization.html) on how to further enhance your interactive dashboard.

[Comer2014] Comer, Kenneth W. “Who Goes First? An Examination of the Impact of Activation on Outcome Behavior in AgentBased Models.” George Mason University, 2014. http://mars.gmu.edu/bitstream/handle/1920/9070/Comer_gmu_0883E_10539.pdf

[Dragulescu2002] Drăgulescu, Adrian A., and Victor M. Yakovenko. “Statistical Mechanics of Money, Income, and Wealth: A Short Survey.” arXiv Preprint Cond-mat/0211175, 2002. http://arxiv.org/abs/cond-mat/0211175.
