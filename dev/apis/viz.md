# Viz

`modelly.viz` draws models in the browser and in notebooks. The names most models need are exported by the package itself: `from modelly.viz import SolaraViz, SpaceRenderer`.

Module

Contents

modelly.viz.solara

SolaraViz, the model controller, parameter inputs and Slider

modelly.viz.components

make_space_component, make_plot_component

modelly.viz.render

SpaceRenderer, the portrayal styles, backends and space drawers

modelly.viz.mpl

matplotlib backend, draw_space and plot components

modelly.viz.altair

Altair backend and plot components

modelly.viz.console

CommandConsole

⚠️ **Important note for SolaraViz users**

When using **SolaraViz**, Modelly models must be instantiated **using keyword arguments only**. SolaraViz creates model instances internally via keyword-based parameters, and positional arguments are **not supported**.

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

- [Basic Visualization](https://remipelloux.github.io/Modelly/dev/tutorials/6_visualization_basic.html)
- [Dynamic Agent Visualization](https://remipelloux.github.io/Modelly/dev/tutorials/7_visualization_dynamic_agents.html)
- [Custom Visualization Components](https://remipelloux.github.io/Modelly/dev/tutorials/10_visualization_custom.html)

## Solara app

Modelly visualization module for creating interactive model visualizations.

This module provides components to create browser- and Jupyter notebook-based visualizations of Modelly models, allowing users to watch models run step-by-step and interact with model parameters.

**Key features:**

- SolaraViz: Main component for creating visualizations, supporting grid displays and plots
- ModelController: Handles model execution controls (step, play, pause, reset)
- UserInputs: Generates UI elements for adjusting model parameters

The module uses Solara for rendering in Jupyter notebooks or as standalone web applications. It supports various types of visualizations including matplotlib plots, agent grids, and custom visualization components.

**Usage:**

1. Define an agent_portrayal function to specify how agents should be displayed
1. Set up model_params to define adjustable parameters
1. Create a SolaraViz instance with your model, parameters, and desired measures
1. Display the visualization in a Jupyter notebook or run as a Solara app

See the Visualization Tutorial and example models for more details.

#### `check_param_is_fixed(param)`

Check if a parameter is fixed (not user-adjustable).

**Parameters:**

**param** – Parameter to check

**Returns:**

True if parameter is fixed, False otherwise

**Return type:**

[bool](https://docs.python.org/3/builtins/functions.html#bool)

#### `copy_renderer(renderer: SpaceRenderer, model: Model)`

Create a new renderer instance with the same configuration as the original.

#### `create_space_component(renderer: SpaceRenderer)`

Create a space visualization component for the given renderer.

#### `make_initial_grid_layout(num_components)`

Create an initial grid layout for visualization components.

**Parameters:**

**num_components** – Number of components to display

**Returns:**

Initial grid layout configuration

**Return type:**

[list](https://docs.python.org/3/builtins/stdtypes.html#list)

#### `split_model_params(model_params)`

Split model parameters into user-adjustable and fixed parameters.

**Parameters:**

**model_params** – Dictionary of all model parameters

**Returns:**

(user_adjustable_params, fixed_params)

**Return type:**

[tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)

Custom visualization components.

#### `make_plot_component(measure: str | dict[str, str] | list[str] | tuple[str], post_process: Callable | None = None, backend: str = 'matplotlib', page: int = 0, **plot_drawing_kwargs)`

Create a plotting function for a specified measure using the specified backend.

**Parameters:**

- **measure** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | *[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*] **| *[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*] **| *[*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – Measure(s) to plot.
- **post_process** – a user-specified callable to do post-processing called with the Axes instance.
- **backend** – the backend to use {“matplotlib”, “altair”}
- **page** – Page number where the plot should be displayed (default 0).
- **plot_drawing_kwargs** – additional keyword arguments to pass onto the backend specific function for making a plotting component

**Returns:**

A tuple of a function and page number that creates a plot component on that specific page.

**Return type:**

(function, page)

#### `make_space_component(agent_portrayal: Callable | None = None, property_layer_portrayal: dict | None = None, post_process: Callable | None = None, backend: str = 'matplotlib', **space_drawing_kwargs) → SpaceMatplotlib | SpaceAltair`

Create a Matplotlib-based space visualization component.

**Parameters:**

- **agent_portrayal** – Function to portray agents.
- **property_layer_portrayal** – Dictionary of property_layer portrayal specifications
- **post_process** – a callable that will be called with the Axes instance. Allows for fine-tuning plots (e.g., control ticks)
- **backend** – the backend to use {“matplotlib”, “altair”}
- **space_drawing_kwargs** – additional keyword arguments to be passed on to the underlying backend specific space drawer function. See the functions for drawing the various spaces for the appropriate backend further details.

**Returns:**

A function that creates a space component

**Return type:**

function

## User parameters

Solara visualization related helper classes.

#### `class UserParam`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

UserParam.

#### `maybe_raise_error(param_type, valid)`

#### `class Slider(label='', value=None, min=None, max=None, step=1, dtype=None)`

Bases: [`UserParam`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.solara.params.UserParam)

A number-based slider input with settable increment.

Example: slider_option = Slider(“My Slider”, value=123, min=10, max=200, step=0.1)

**Parameters:**

- **label** – The displayed label in the UI
- **value** – The initial value of the slider
- **min** – The minimum possible value of the slider
- **max** – The maximum possible value of the slider
- **step** – The step between min and max for a range of possible values
- **dtype** – either int or float

Initializes a slider.

**Parameters:**

- **label** – The displayed label in the UI
- **value** – The initial value of the slider
- **min** – The minimum possible value of the slider
- **max** – The maximum possible value of the slider
- **step** – The step between min and max for a range of possible values
- **dtype** – either int or float

#### `get(attr)`

## Matplotlib-based visualizations

Matplotlib based solara components for visualization MODELLY spaces and plots.

#### `make_space_matplotlib(*args, **kwargs)`

#### `make_mpl_space_component(agent_portrayal: Callable | None = None, property_layer_portrayal: dict | None = None, post_process: Callable | None = None, **space_drawing_kwargs) → SpaceMatplotlib`

Create a Matplotlib-based space visualization component.

**Parameters:**

- **agent_portrayal** – Function to portray agents.
- **property_layer_portrayal** – Dictionary of property_layer portrayal specifications
- **post_process** – a callable that will be called with the Axes instance. Allows for fine tuning plots (e.g., control ticks)
- **space_drawing_kwargs** – additional keyword arguments to be passed on to the underlying space drawer function. See the functions for drawing the various spaces for further details.

`agent_portrayal` is called with an agent and should return a dict. Valid fields in this dict are “color”, “size”, “marker”, “zorder”, alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

**Returns:**

A function that creates a SpaceMatplotlib component

**Return type:**

function

#### `make_plot_measure(*args, **kwargs)`

#### `make_mpl_plot_component(measure: str | dict[str, str] | list[str] | tuple[str], post_process: Callable | None = None, page: int = 0, save_format='png')`

Create a plotting function for a specified measure.

**Parameters:**

- **measure** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | *[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*] **| *[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*] **| *[*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – Measure(s) to plot.
- **post_process** – a user-specified callable to do post-processing called with the Axes instance.
- **page** – Page number where the plot should be displayed.
- **save_format** – save format of figure in solara backend

**Returns:**

A tuple of a function that creates a PlotMatplotlib component and a page number.

**Return type:**

(function, page)

Helper functions for drawing modelly spaces with matplotlib.

These functions are used by the provided matplotlib components, but can also be used to quickly visualize a space with matplotlib for example when creating a mp4 of a movie run or when needing a figure for a paper.

#### `class HexGrid(dimensions: ~collections.abc.Sequence[int], torus: bool = False, capacity: float | None = None, random: ~random.Random | None = None, cell_klass: type[~modelly.space.grid.grids.T] = <class 'modelly.space.cells.cell.Cell'>)`

Bases: [`Grid`](https://remipelloux.github.io/Modelly/dev/apis/space.html#modelly.space.grid.base.Grid)[`T`]

A Grid with hexagonal tilling of the space.

Functions according to even-r rules. See [https://www.redblobgames.com/grids/hexagons/#neighbors-offset](https://www.redblobgames.com/grids/hexagons/#neighbors-offset) for more.

Note

When torus=True, both width and height must be even.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If torus=True and either width or height is odd.

Initialize the hex grid.

**Parameters:**

- **dimensions** – the dimensions of the space
- **torus** – whether the space wraps
- **capacity** – capacity of the grid cell
- **random** – a random number generator
- **cell_klass** – the base class to use for the cells

#### `find_nearest_cell(position: ndarray) → T`

Find the hex cell at the given position.

#### `class Network(G: Any, capacity: int | None = None, random: Random | None = None, cell_klass: type[Cell] = <class 'modelly.space.cells.cell.Cell'>, layout: Mapping | Callable | None = None)`

Bases: [`DiscreteSpace`](https://remipelloux.github.io/Modelly/dev/apis/space.html#modelly.space.base.DiscreteSpace)[[`Cell`](https://remipelloux.github.io/Modelly/dev/apis/space.html#modelly.space.cells.cell.Cell)]

A networked discrete space.

A Networked grid.

**Parameters:**

- **G** – a NetworkX Graph instance.
- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the capacity of the cell
- **random** (*Random*) – a random number generator
- **cell_klass** ([*type*](https://docs.python.org/3/builtins/functions.html#type)*[*[*Cell*](https://remipelloux.github.io/Modelly/dev/apis/space.html#modelly.space.cells.cell.Cell)*]*) – The base Cell class to use in the Network
- **layout** – A dictionary mapping node IDs to physical positions (x, y), or a callable that generates them (e.g. nx.spring_layout). It defaults to nx.circular_layout This ensures all nodes possess physical (x, y) positions for visualization and spatial queries without introducing performance bottlenecks on large graphs

#### `find_nearest_cell(position: ndarray) → Cell`

Find the network node nearest to the given position.

Only works for spatial networks (networks with node positions).

Note

The KD-Tree index is rebuilt lazily. If cells were added or removed since the previous spatial query, this method rebuilds the KD-Tree before performing the nearest-neighbor lookup.

**Parameters:**

**position** – Physical position [x, y]

**Returns:**

The node closest to the position

**Return type:**

[Cell](https://remipelloux.github.io/Modelly/dev/apis/space.html#modelly.space.cells.cell.Cell)

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If network is not spatial

#### `add_cell(cell: Cell)`

Add a cell to the space.

#### `remove_cell(cell: Cell)`

Remove a cell from the space.

#### `add_connection(cell1: Cell, cell2: Cell)`

Add a connection between the two cells.

#### `remove_connection(cell1: Cell, cell2: Cell)`

Remove a connection between the two cells.

#### `collect_agent_data(space: OrthogonalMooreGrid | OrthogonalVonNeumannGrid | HexGrid | Network | ContinuousSpace | VoronoiGrid, agent_portrayal: Callable, default_size: float | None = None) → dict`

Collect the plotting data for all agents in the space.

**Parameters:**

- **space** – The space containing the Agents.
- **agent_portrayal** – A callable that is called with the agent and returns a AgentPortrayalStyle
- **default_size** – default size

agent_portrayal should return a AgentPortrayalStyle, limited to size (size of marker), color (color of marker), zorder (z-order), marker (marker style), alpha, linewidths, and edgecolors.

#### `draw_continuous_space(space: ContinuousSpace, agent_portrayal: Callable, ax: Axes | None = None, **kwargs)`

Visualize a continuous space.

**Parameters:**

- **space** – the space to visualize
- **agent_portrayal** – a callable that is called with the agent and returns a AgentPortrayalStyle
- **ax** – a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
- **kwargs** – additional keyword arguments passed to ax.scatter

**Returns:**

Returns the Axes object with the plot drawn onto it.

`agent_portrayal` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are “color”, “size”, “marker”, “zorder”, alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

#### `draw_hex_grid(space: HexGrid, agent_portrayal: Callable, ax: Axes | None = None, draw_grid: bool = True, **kwargs)`

Visualize a hex grid.

**Parameters:**

- **space** – the space to visualize
- **agent_portrayal** – a callable that is called with the agent and returns a AgentPortrayalStyle
- **ax** – a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
- **draw_grid** – whether to draw the grid
- **kwargs** – additional keyword arguments passed to ax.scatter

**Returns:**

Returns the Axes object with the plot drawn onto it.

`agent_portrayal` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are “color”, “size”, “marker”, “zorder”, alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

#### `draw_network(space: Network, agent_portrayal: Callable, ax: Axes | None = None, draw_grid: bool = True, **kwargs)`

Visualize a network space.

**Parameters:**

- **space** – the space to visualize
- **agent_portrayal** – a callable that is called with the agent and returns a AgentPortrayalStyle
- **ax** – a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
- **draw_grid** – whether to draw the grid
- **kwargs** – additional keyword arguments passed to ax.scatter

**Returns:**

Returns the Axes object with the plot drawn onto it.

`agent_portrayal` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are “color”, “size”, “marker”, “zorder”, alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

#### `draw_orthogonal_grid(space: OrthogonalMooreGrid | OrthogonalVonNeumannGrid, agent_portrayal: Callable, ax: Axes | None = None, draw_grid: bool = True, **kwargs)`

Visualize a orthogonal grid.

**Parameters:**

- **space** – the space to visualize
- **agent_portrayal** – a callable that is called with the agent and returns a AgentPortrayalStyle
- **ax** – a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
- **draw_grid** – whether to draw the grid
- **kwargs** – additional keyword arguments passed to ax.scatter

**Returns:**

Returns the Axes object with the plot drawn onto it.

`agent_portrayal` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are “color”, “size”, “marker”, “zorder”, alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

#### `draw_property_layers(space, property_layer_portrayal: dict[str, dict[str, Any]] | Callable, ax: Axes)`

Draw Property Layers on the given axes.

**Parameters:**

- **space** – The space having the property_layer.
- **property_layer_portrayal** (*Callable*) – A function that accepts a property layer object and returns either a PropertyLayerStyle object defining its visualization, or None to skip drawing this particular layer.
- **ax** (*matplotlib.axes.Axes*) – The axes to draw on.

#### `draw_space(space, agent_portrayal: Callable, property_layer_portrayal: Callable | None = None, ax: Axes | None = None, **space_drawing_kwargs)`

Draw a Matplotlib-based visualization of the space.

**Parameters:**

- **space** – the space of the modelly model
- **agent_portrayal** – A callable that returns a AgnetPortrayalStyle specifying how to show the agent
- **property_layer_portrayal** – A callable that returns a PropertyLayerStyle specifying how to show the property layer
- **ax** – the axes upon which to draw the plot
- **space_drawing_kwargs** – any additional keyword arguments to be passed on to the underlying function for drawing the space.

**Returns:**

Returns the Axes object with the plot drawn onto it.

`agent_portrayal` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are “color”, “size”, “marker”, “zorder”, alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

#### `draw_voronoi_grid(space: VoronoiGrid, agent_portrayal: Callable, ax: Axes | None = None, draw_grid: bool = True, **kwargs)`

Visualize a voronoi grid.

**Parameters:**

- **space** – the space to visualize
- **agent_portrayal** – a callable that is called with the agent and returns a AgentPortrayalStyle
- **ax** – a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
- **draw_grid** – whether to draw the grid or not
- **kwargs** – additional keyword arguments passed to ax.scatter

**Returns:**

Returns the Axes object with the plot drawn onto it.

`agent_portrayal` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are “color”, “size”, “marker”, “zorder”, alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

## Altair-based visualizations

Altair based solara components for visualization modelly spaces.

#### `chart_property_layers(space, property_layer_portrayal, chart_width, chart_height)`

Creates Property Layers in the Altair Components.

**Parameters:**

- **space** – the ContinuousSpace instance
- **property_layer_portrayal** – Dictionary of property_layer portrayal specifications
- **chart_width** – width of the agent chart to maintain consistency with the property_layer charts
- **chart_height** – height of the agent chart to maintain consistency with the property_layer charts

**Returns:**

Altair Chart

#### `make_altair_plot_component(measure: str | dict[str, str] | list[str] | tuple[str], post_process: Callable | None = None, page: int = 0, grid=False)`

Create a plotting function for a specified measure.

**Parameters:**

- **measure** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | *[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*] **| *[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*] **| *[*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – Measure(s) to plot.
- **post_process** – a user-specified callable to do post-processing called with the Axes instance.
- **page** – Page number where the plot should be displayed.
- **grid** – Bool to draw grid or not.

**Returns:**

A tuple of a function that creates a PlotAltair component and a page number.

**Return type:**

(function, page)

#### `make_altair_space(agent_portrayal, property_layer_portrayal=None, post_process=None, **space_drawing_kwargs)`

Create an Altair-based space visualization component.

**Parameters:**

- **agent_portrayal** – Function to portray agents.
- **property_layer_portrayal** – Dictionary of property_layer portrayal specifications
- **post_process** – A user specified callable that will be called with the Chart instance from Altair. Allows for fine tuning plots (e.g., control ticks)
- **space_drawing_kwargs** – not yet implemented

`agent_portrayal` is called with an agent and should return a dict. Valid fields in this dict are “color”, “size”, “marker”, and “zorder”. Other field are ignored and will result in a user warning.

**Returns:**

A function that creates a SpaceMatplotlib component

**Return type:**

function

#### `make_space_altair(*args, **kwargs)`

## Command console

A command console interface for interactive Python code execution in the browser.

This module provides a set of classes and functions to create an interactive Python console that can be embedded in a web browser. It supports command history, multi-line code blocks, and special commands for console management.

Notes

- The console supports multi-line code blocks with proper indentation
- Output is captured and displayed with appropriate formatting
- Error messages are displayed in red with distinct styling
- The console maintains a history of commands and their outputs

#### `class CaptureOutput`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A context manager for capturing stdout and stderr output.

This class provides a way to capture output that would normally be printed to stdout and stderr during the execution of code within its context.

Initialize the CaptureOutput context manager with empty string buffers.

#### `get_output()`

Retrieve and clear the captured output.

**Returns:**

A pair of strings (stdout_output, stderr_output)

**Return type:**

[tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)

#### `class ConsoleEntry(command: str, output: str = '', is_error: bool = False, is_continuation: bool = False)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A class to store command console entries.

**Variables:**

- **command** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The command entered
- **output** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The output of the command
- **is_error** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – Whether the entry represents an error
- **is_continuation** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – Whether the entry is a continuation of previous command

#### `command: str`

#### `output: str = ''`

#### `is_error: bool = False`

#### `is_continuation: bool = False`

#### `class ConsoleManager(model=None, additional_imports=None)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A console manager for executing Python code interactively.

This class provides functionality to execute Python code in an interactive console environment, maintain command history, and handle multi-line code blocks.

**Variables:**

- **locals_dict** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)) – Dictionary containing local variables available to the console
- **console** ([*InteractiveConsole*](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.console.console.InteractiveConsole)) – Python’s interactive console instance
- **buffer** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)) – Buffer for storing multi-line code blocks
- **history** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*ConsoleEntry*](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.console.console.ConsoleEntry)*]*) – List of console entries containing commands and their outputs

Special commands: `history` shows the command history, `cls` clears the console screen and `tips` shows the available commands and usage tips.

Example

```default
>>> console = ConsoleManager(model=my_model)
>>> console.execute_code("print('hello world')", set_input_callback)
```

Initialize the console manager with the provided model and imports.

#### `history: list[ConsoleEntry]`

#### `execute_code(code_line: str, set_input_text: Callable[[str], None]) → None`

Execute the provided code line and update the console history.

#### `clear_console() → None`

Clear the console history and reset the console state.

#### `get_entries() → list[ConsoleEntry]`

Get the list of console entries.

#### `prev_command(current_text: str, set_input_text: Callable[[str], None]) → None`

Navigate to previous command in history.

#### `next_command(set_input_text: Callable[[str], None]) → None`

Navigate to next command in history.

#### `class InteractiveConsole(locals_dict=None)`

Bases: [`InteractiveConsole`](https://docs.python.org/3/library/code.html#code.InteractiveConsole)

A custom interactive Python console with output capturing capabilities.

This class extends code.InteractiveConsole to provide output capturing functionality when executing Python code interactively.

**Parameters:**

**locals_dict** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*, **optional*) – Dictionary of local variables. Defaults to None.

Initialize the InteractiveConsole with the provided locals dictionary.

#### `push(line)`

Push a line to the command interpreter and execute it.

This method captures the output of the executed command and returns both the ‘more’ flag and the captured output.

**Parameters:**

**line** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The line of code to be executed.

**Returns:**

**A tuple containing:**

- more (bool): Flag indicating if more input is needed
- str: The captured output from executing the command

**Return type:**

[tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)

#### `format_command_html(entry)`

Format the command part of a console entry as HTML.

#### `format_output_html(entry)`

Format the output part of a console entry as HTML.

## Portrayal components

Portrayal Components Module.

This module defines data structures for styling visual elements in Modelly agent-based model visualizations. It provides user-facing classes to specify how agents and property layers should appear in the rendered space.

Classes: 1. AgentPortrayalStyle: Controls the appearance of individual agents (e.g., color, shape, size, etc.). 2. PropertyLayerStyle: Controls the appearance of background property layers (e.g., color gradients or uniform fills).

These components are designed to be passed into Modelly visualizations to customize and standardize how data is presented.

This module is the one portrayal API every backend (Matplotlib, Altair) and Modelly Studio share: the style classes, their defaults, the conversion of legacy portrayal dicts, and `ClassColours`, the default portrayal that colours agents by class.

#### `class AgentPortrayalStyle(x: float | None = None, y: float | None = None, color: str | tuple | int | float | None = 'tab:blue', marker: str | None = 'o', size: int | float | None = 50, zorder: int | None = 1, alpha: float | None = 1.0, edgecolors: str | tuple | None = None, linewidths: float | int | None = 1.0, tooltip: dict | None = None, filled: bool = True)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Represents the visual styling options for an agent in a visualization.

User facing component to control how agents are drawn. Allows specifying properties like color, size, marker shape, position, and other plot attributes.

x, y are determined automatically according to the agent’s type (normal/CellAgent) and position in the space if not manually declared.

Example

```default
>>> def agent_portrayal(agent):
>>>     return AgentPortrayalStyle(
>>>         x=agent.cell.coordinate[0],
>>>         y=agent.cell.coordinate[1],
>>>         color="red",
>>>         marker="o",
>>>         size=20,
>>>         zorder=2,
>>>         alpha=0.8,
>>>         edgecolors="black",
>>>         linewidths=1.5
>>>     )
>>>
>>> # or for a default agent portrayal
>>> def agent_portrayal(agent):
>>>     return AgentPortrayalStyle()
```

#### `x: float | None = None`

#### `y: float | None = None`

#### `color: str | tuple | int | float | None = 'tab:blue'`

#### `marker: str | None = 'o'`

#### `size: int | float | None = 50`

#### `zorder: int | None = 1`

#### `alpha: float | None = 1.0`

#### `edgecolors: str | tuple | None = None`

#### `linewidths: float | int | None = 1.0`

#### `tooltip: dict | None = None`

#### `filled: bool = True`

#### `update(*updates_fields: tuple[str, Any])`

Updates attributes from variable (field_name, new_value) tuple arguments.

Example

```default
>>> def agent_portrayal(agent):
>>>     primary_style = AgentPortrayalStyle(color="blue", marker="^", size=10, x=agent.pos[0], y=agent.pos[1])
>>>     if agent.type == 1:
>>>         primary_style.update(("color", "red"), ("size", 30))
>>>     return primary_style
```

#### `style_defaults() → dict[str, Any]`

Return the default value of every AgentPortrayalStyle field, by field name.

#### `warn_dict_portrayal(stacklevel: int = 3) → None`

Warn that returning a dict from agent_portrayal is deprecated.

#### `dict_to_style(portray_input: dict, position, style_fields: dict) → tuple[AgentPortrayalStyle, list[str]]`

Build an AgentPortrayalStyle from a legacy portrayal dict.

Returns the style and the keys of the dict it did not use, for the caller to warn about.

#### `class ClassColours(palette: Sequence[str] | None = None, size: float = 50)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The default portrayal: one colour per agent class, in the order classes are met.

Any model can be drawn with it, which is what Modelly Studio does when no portrayal is given. The palette defaults to Okabe-Ito, which stays distinct with colour-blindness.

**Parameters:**

- **palette** – The colours to cycle through, one per agent class.
- **size** – The marker size of every agent.

Colour agents from `palette` (Okabe-Ito when None).

#### `classes: dict[str, str]`

#### `class PropertyLayerStyle(colormap: str | None = None, color: str | None = None, alpha: float = 0.8, colorbar: bool = True, vmin: float | None = None, vmax: float | None = None)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Represents the visual styling options for a property layer in a visualization.

User facing component to control how property layers are drawn. Allows specifying properties like colormap, single color, value limits (vmin, vmax), transparency (alpha) and colorbar visibility.

Note: vmin and vmax are the lower and upper bounds for the colorbar and the data is normalized between these values for color/colormap rendering. If they are not declared the values are automatically determined from the data range.

Note: You can specify either a ‘colormap’ (for varying data) or a single ‘color’ (for a uniform layer appearance), but not both simultaneously.

Example

```default
>>> def property_layer_portrayal(layer):
>>>     return PropertyLayerStyle(colormap="viridis", vmin=0, vmax=100, alpha=0.5, colorbar=True)
>>> # or for a uniform color layer
>>> def property_layer_portrayal(layer):
>>>     return PropertyLayerStyle(color="lightblue", alpha=0.8, colorbar=False)
```

#### `colormap: str | None = None`

#### `color: str | None = None`

#### `alpha: float = 0.8`

#### `colorbar: bool = True`

#### `vmin: float | None = None`

#### `vmax: float | None = None`

#### `property_layer_dict_to_callable(portrayal_dict: dict[str, dict[str, Any]])`

Convert a legacy property_layer_portrayal dict to a PropertyLayerStyle callable.

**Parameters:**

**portrayal_dict** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)) – Dictionary with portrayal parameters per layer name.

**Returns:**

Function that returns a PropertyLayerStyle, or None for a layer missing from the dict.

**Return type:**

Callable

#### `as_property_layer_callable(portrayal)`

Return a property layer portrayal as a callable returning PropertyLayerStyle.

A legacy dict is converted, a PropertyLayerStyle is wrapped in a callable that always returns it, and anything else (already a callable) is returned as-is.

## Backends

Abstract base class for visualization backends in Modelly.

This module provides the foundational interface for implementing various visualization backends for Modelly agent-based models.

#### `class AbstractRenderer(space_drawer)`

Bases: [`ABC`](https://docs.python.org/3/library/abc.html#abc.ABC)

Abstract base class for visualization backends.

This class defines the interface for rendering Modelly spaces and agents. For details on the methods checkout specific backend implementations.

Initialize the renderer.

**Parameters:**

- **space_drawer** – Object responsible for drawing space elements. Checkout SpaceDrawer
- **functions.** (*for more details on the detailed implementations** of **the drawing*)

#### `abstractmethod initialize_canvas()`

Set up the drawing canvas.

#### `abstractmethod draw_structure(**kwargs)`

Draw the space structure.

**Parameters:**

****kwargs** – Structure drawing configuration options.

#### `abstractmethod collect_agent_data(space, agent_portrayal, default_size=None)`

Collect plotting data for all agents in the space.

**Parameters:**

- **space** – The Modelly space containing agents.
- **agent_portrayal** (*Callable*) – Function that returns AgentPortrayalStyle for each agent.
- **default_size** ([*float*](https://docs.python.org/3/builtins/functions.html#float)*, **optional*) – Default marker size if not specified in portrayal.

**Returns:**

Dictionary containing agent plotting data arrays with keys:

**Return type:**

[dict](https://docs.python.org/3/builtins/stdtypes.html#dict)

#### `abstractmethod draw_agents(arguments, **kwargs)`

Drawing agents on space.

**Parameters:**

- **arguments** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)) – Dictionary containing agent data.
- ****kwargs** – Additional drawing configuration options.

#### `abstractmethod draw_property_layer(space, property_layers, property_layer_portrayal)`

Draw property layers on the visualization.

**Parameters:**

- **space** – The model’s space object.
- **property_layers** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)) – Dictionary of property layers to visualize.
- **property_layer_portrayal** (*Callable*) – Function that returns PropertyLayerStyle.

#### `class AltairBackend(space_drawer)`

Bases: [`AbstractRenderer`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.backend.AbstractRenderer)

Altair-based renderer for Modelly spaces.

This module provides an Altair-based renderer for visualizing Modelly model spaces, agents, and property layers with interactive charting capabilities.

Initialize the renderer.

**Parameters:**

- **space_drawer** – Object responsible for drawing space elements. Checkout SpaceDrawer
- **functions.** (*for more details on the detailed implementations** of **the drawing*)

#### `initialize_canvas() → None`

Initialize the Altair canvas.

#### `draw_structure(**kwargs) → Chart`

Draw the space structure using Altair.

**Parameters:**

- ****kwargs** – Additional arguments passed to the space drawer.
- ****kwargs.** (*Checkout respective SpaceDrawer class on details on how to pass*)

**Returns:**

The Altair chart representing the space structure.

**Return type:**

alt.Chart

#### `collect_agent_data(space, agent_portrayal: Callable, default_size: float | None = None)`

Collect plotting data for all agents in the space for Altair.

**Parameters:**

- **space** – The Modelly space containing agents.
- **agent_portrayal** – Callable that returns AgentPortrayalStyle for each agent.
- **default_size** – Default marker size if not specified in portrayal.

**Returns:**

Dictionary containing agent plotting data arrays.

**Return type:**

[dict](https://docs.python.org/3/builtins/stdtypes.html#dict)

#### `draw_agents(arguments, chart_width: int = 450, chart_height: int = 350, **kwargs)`

Draw agents using Altair backend.

**Parameters:**

- **arguments** – Dictionary containing agent data arrays.
- **chart_width** – Width of the chart.
- **chart_height** – Height of the chart.
- ****kwargs** – `title`, `xlabel`, `ylabel`, `cmap`, `vmin` and `vmax` customise the chart; any other keyword is an Altair point-mark property (for example `strokeDash`) passed to `mark_point`.
- ****kwargs.** (*Checkout respective SpaceDrawer class on details on how to pass*)

**Returns:**

The Altair chart representing the agents, or None if no agents.

**Return type:**

alt.Chart

#### `draw_property_layer(space, property_layers: dict[str, ndarray], property_layer_portrayal: Callable, chart_width: int = 450, chart_height: int = 350)`

Draw property layers using Altair backend.

**Parameters:**

- **space** – The Modelly space object containing the property layers.
- **property_layers** – A dictionary mapping property_layer names to numpy arrays.
- **property_layer_portrayal** – A function that returns PropertyLayerStyle that contains the visualization parameters.
- **chart_width** – The width of the chart.
- **chart_height** – The height of the chart.

**Returns:**

A tuple containing the base chart and the color bar chart.

**Return type:**

alt.Chart

#### `class MatplotlibBackend(space_drawer)`

Bases: [`AbstractRenderer`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.backend.AbstractRenderer)

Matplotlib-based renderer for Modelly spaces.

Provides visualization capabilities using Matplotlib for rendering space structures, agents, and property layers.

Initialize the Matplotlib backend.

**Parameters:**

**space_drawer** – An instance of a SpaceDrawer class that handles the drawing of the space structure.

#### `initialize_canvas(ax=None)`

Initialize the matplotlib canvas.

**Parameters:**

**ax** (*matplotlib.axes.Axes**, **optional*) – Existing axes to use. If None, creates new figure and axes.

#### `draw_structure(**kwargs)`

Draw the space structure using matplotlib.

**Parameters:**

- ****kwargs** – Additional arguments passed to the space drawer.
- ****kwargs.** (*Checkout respective SpaceDrawer class on details on how to pass*)

**Returns:**

The matplotlib axes with the drawn structure.

#### `collect_agent_data(space, agent_portrayal, default_size=None)`

Collect plotting data for all agents in the space.

**Parameters:**

- **space** – The Modelly space containing agents.
- **agent_portrayal** (*Callable*) – Function that returns AgentPortrayalStyle for each agent.
- **default_size** ([*float*](https://docs.python.org/3/builtins/functions.html#float)*, **optional*) – Default marker size if not specified in portrayal.

**Returns:**

Dictionary containing agent plotting data arrays.

**Return type:**

[dict](https://docs.python.org/3/builtins/stdtypes.html#dict)

#### `draw_agents(arguments, **kwargs)`

Draw agents on the backend’s axes - optimized version.

**Parameters:**

- **arguments** – Dictionary containing agent data arrays.
- ****kwargs** – Additional keyword arguments for customization.
- ****kwargs.** (*Checkout respective SpaceDrawer class on details on how to pass*)

**Returns:**

The Matplotlib Axes with the agents drawn upon it.

**Return type:**

matplotlib.axes.Axes

#### `draw_property_layer(space, property_layers, property_layer_portrayal)`

Draw property layers using matplotlib backend.

**Parameters:**

- **space** – The Modelly space object.
- **property_layers** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)) – Dictionary of property layers to visualize.
- **property_layer_portrayal** (*Callable*) – Function that returns PropertyLayerStyle.

**Returns:**

(matplotlib.axes.Axes, colorbar) - The matplotlib axes and colorbar objects.

**Return type:**

[tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)

## Space renderer

Space rendering module for Modelly visualizations.

This module provides functionality to render Modelly model spaces with different backends, supporting various space types and visualization components.

#### `class SpaceRenderer(model: Model, backend: Literal['matplotlib', 'altair'] | None = 'matplotlib')`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Renders Modelly spaces using different visualization backends.

Supports multiple space types and backends for flexible visualization of agent-based models.

Initialize the space renderer.

**Parameters:**

- **model** (*modelly.Model*) – The Modelly model to render.
- **backend** (*Literal**[**"matplotlib"**, **"altair"**] **| **None*) – The visualization backend to use.

#### `setup_structure(**kwargs) → SpaceRenderer`

Setup the space structure without drawing.

**Parameters:**

- ****kwargs** – Additional keyword arguments for the setup function. For ContinuousSpace, you may pass `viz_dims=(i, j)` to select which two dimensions are projected to x/y.
- ****kwargs.** (*Checkout respective SpaceDrawer class on details on how to pass*)

**Returns:**

The current instance for method chaining.

**Return type:**

[SpaceRenderer](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.renderer.SpaceRenderer)

#### `setup_agents(agent_portrayal: Callable, **kwargs) → SpaceRenderer`

Setup agents on the space without drawing.

**Parameters:**

- **agent_portrayal** (*Callable*) – Function that takes an agent and returns AgentPortrayalStyle.
- ****kwargs** – Additional keyword arguments for the setup function.
- ****kwargs.** (*Checkout respective SpaceDrawer class on details on how to pass*)

**Returns:**

The current instance for method chaining.

**Return type:**

[SpaceRenderer](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.renderer.SpaceRenderer)

#### `setup_property_layer(property_layer_portrayal: Callable | dict | PropertyLayerStyle) → SpaceRenderer`

Setup property layers on the space without drawing.

**Parameters:**

**property_layer_portrayal** (*Callable** | *[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)* | *[*PropertyLayerStyle*](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.portrayal.PropertyLayerStyle)) – A PropertyLayerStyle, a function that produces a PropertyLayerStyle instance, or a dictionary specifying portrayal parameters.

**Returns:**

The current instance for method chaining.

**Return type:**

[SpaceRenderer](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.renderer.SpaceRenderer)

#### `draw_structure(**kwargs)`

Draw the space structure.

**Parameters:**

****kwargs** – (Deprecated) Additional keyword arguments for drawing. Use setup_structure() instead.

**Returns:**

The visual representation of the space structure.

#### `draw_agents(agent_portrayal=None, **kwargs)`

Draw agents on the space.

**Parameters:**

- **agent_portrayal** – (Deprecated) Function that takes an agent and returns AgentPortrayalStyle. Use setup_agents() instead.
- ****kwargs** – (Deprecated) Additional keyword arguments for drawing.

**Returns:**

The visual representation of the agents.

#### `draw_property_layer(property_layer_portrayal=None)`

Draw property layers on the space.

**Parameters:**

- **property_layer_portrayal** – (Deprecated) A PropertyLayerStyle, a function that produces
- **instance** (*a PropertyLayerStyle*)
- **parameters.** (*or a dictionary specifying portrayal*)
- **instead.** (*Use setup_property_layer**(**)*)

**Returns:**

The visual representation of the property layers.

**Raises:**

[**Exception**](https://docs.python.org/3/builtins/exceptions.html#Exception) – If no property layers are found on the space.

#### `render(agent_portrayal=None, property_layer_portrayal=None, **kwargs)`

Render the complete space with structure, agents, and property layers.

**Parameters:**

- **agent_portrayal** – (Deprecated) Function for agent portrayal. Use setup_agents() instead.
- **property_layer_portrayal** – (Deprecated) Function for property layer portrayal. Use setup_property_layer() instead.
- ****kwargs** – (Deprecated) Additional keyword arguments.

#### `property canvas`

Get the current canvas object.

**Returns:**

The backend-specific canvas object.

#### `property post_process`

Get the current post-processing function.

**Returns:**

The post-processing function, or None if not set.

**Return type:**

Callable | None

## Space drawers

Base class and shared helpers for the space drawers.

#### `class BaseSpaceDrawer(space)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Base class for all space drawers.

Initialize the base space drawer.

**Parameters:**

**space** – Grid/Space type to draw.

#### `get_viz_limits()`

Get visualization limits for the space.

**Returns:**

A tuple of (xmin, xmax, ymin, ymax) for visualization limits.

#### `axes_with_figure_kwargs(ax, draw_space_kwargs)`

Pop figsize/dpi from the kwargs and create axes when none is given.

#### `chart_properties(chart_width, chart_height, draw_chart_kwargs)`

Return the chart properties: width, height, then the remaining kwargs.

#### `line_mark_kwargs(draw_chart_kwargs)`

Pop the dashed line mark styling from the kwargs, with defaults.

Drawer for orthogonal grid spaces.

#### `class OrthogonalSpaceDrawer(space: OrthogonalMooreGrid | OrthogonalVonNeumannGrid)`

Bases: [`BaseSpaceDrawer`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.drawers.base.BaseSpaceDrawer)

Drawer for orthogonal grid spaces (SingleGrid, MultiGrid, Moore, VonNeumann).

Initialize the orthogonal space drawer.

**Parameters:**

**space** – The orthogonal grid space to draw

#### `draw_matplotlib(ax=None, **draw_space_kwargs)`

Draw the orthogonal grid using matplotlib.

**Parameters:**

- **ax** – Matplotlib axes object to draw on
- ****draw_space_kwargs** – Additional keyword arguments for styling.

Examples

figsize=(10, 10), color=”blue”, linewidth=2.

**Returns:**

The modified axes object

#### `draw_altair(chart_width=450, chart_height=350, **draw_chart_kwargs)`

Draw the orthogonal grid using Altair.

**Parameters:**

- **chart_width** – Width for the shown chart
- **chart_height** – Height for the shown chart
- ****draw_chart_kwargs** – Additional keyword arguments for styling the chart.

Examples

width=500, height=500, title=”Grid”.

**Returns:**

Altair chart object

Drawer for hexagonal grid spaces.

#### `class HexSpaceDrawer(space: HexGrid)`

Bases: [`BaseSpaceDrawer`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.drawers.base.BaseSpaceDrawer)

Drawer for hexagonal grid spaces.

Initialize the hexagonal space drawer.

**Parameters:**

**space** – The hexagonal grid space to draw

#### `draw_matplotlib(ax=None, **draw_space_kwargs)`

Draw the hexagonal grid using matplotlib.

**Parameters:**

- **ax** – Matplotlib axes object to draw on
- ****draw_space_kwargs** – Additional keyword arguments for styling.

Examples

figsize=(8, 8), color=”red”, alpha=0.5.

**Returns:**

The modified axes object

#### `draw_altair(chart_width=450, chart_height=350, **draw_chart_kwargs)`

Draw the hexagonal grid using Altair.

**Parameters:**

- **chart_width** – Width for the shown chart
- **chart_height** – Height for the shown chart
- ****draw_chart_kwargs** – Additional keyword arguments for styling the chart.

Examples

- Line properties like color, strokeDash, strokeWidth, opacity.
- Other kwargs (e.g., width, title) apply to the chart.

**Returns:**

Altair chart object representing the hexagonal grid.

Drawer for network spaces.

#### `class NetworkSpaceDrawer(space: Network, layout_alg=<function spring_layout>, layout_kwargs=None)`

Bases: [`BaseSpaceDrawer`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.drawers.base.BaseSpaceDrawer)

Drawer for network-based spaces.

Initialize the network space drawer.

**Parameters:**

- **space** – The network space to draw
- **layout_alg** – NetworkX layout algorithm to use
- **layout_kwargs** – Keyword arguments for the layout algorithm

#### `draw_matplotlib(ax=None, **draw_space_kwargs)`

Draw the network using matplotlib.

**Parameters:**

- **ax** – Matplotlib axes object to draw on.
- ****draw_space_kwargs** – Dictionaries of keyword arguments for styling. Can also handle zorder for both nodes and edges if passed. * `node_kwargs`: A dict passed to nx.draw_networkx_nodes. * `edge_kwargs`: A dict passed to nx.draw_networkx_edges.

**Returns:**

The modified axes object.

#### `draw_altair(chart_width=450, chart_height=350, **draw_chart_kwargs)`

Draw the network using Altair.

**Parameters:**

- **chart_width** – Width for the shown chart
- **chart_height** – Height for the shown chart
- ****draw_chart_kwargs** – Dictionaries for styling the chart. * `node_kwargs`: A dict of properties for the node’s mark_point. * `edge_kwargs`: A dict of properties for the edge’s mark_rule. * Other kwargs (e.g., title, width) are passed to chart.properties().

**Returns:**

Altair chart object representing the network.

Drawer for continuous spaces.

#### `class ContinuousSpaceDrawer(space: ContinuousSpace, viz_dims: tuple[int, int] = (0, 1))`

Bases: [`BaseSpaceDrawer`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.drawers.base.BaseSpaceDrawer)

Drawer for continuous spaces.

Initialize the continuous space drawer.

**Parameters:**

- **space** – The continuous space to draw.
- **viz_dims** – The pair of dimension indices to project onto the x and y axes.

**Raises:**

- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the space has fewer than two dimensions.
- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If viz_dims does not contain exactly two distinct valid indices.

#### `set_viz_dims(viz_dims: tuple[int, int]) → None`

Set which dimensions are visualized on the x and y axes.

**Parameters:**

**viz_dims** – Tuple of two distinct dimension indices.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If viz_dims is invalid for the underlying space.

#### `project(position)`

Project an n-dimensional position onto the configured 2D plane.

#### `draw_matplotlib(ax=None, **draw_space_kwargs)`

Draw the continuous space using matplotlib.

**Parameters:**

- **ax** – Matplotlib axes object to draw on.
- ****draw_space_kwargs** – Keyword arguments for styling the axis frame. You may optionally pass `viz_dims=(i, j)` to select which two dimensions of an n-dimensional space are projected to x/y.

Examples

linewidth=3, color=”green”

**Returns:**

The modified axes object.

#### `draw_altair(chart_width=450, chart_height=350, **draw_chart_kwargs)`

Draw the continuous space using Altair.

**Parameters:**

- **chart_width** – Width for the shown chart.
- **chart_height** – Height for the shown chart.
- ****draw_chart_kwargs** – Keyword arguments for styling the chart’s view properties. You may optionally pass `viz_dims=(i, j)` to select which two dimensions of an n-dimensional space are projected to x/y.

**Returns:**

An Altair Chart object representing the space.

Drawer for Voronoi diagram spaces, with Cohen-Sutherland line clipping.

#### `class VoronoiSpaceDrawer(space: VoronoiGrid)`

Bases: [`BaseSpaceDrawer`](https://remipelloux.github.io/Modelly/dev/apis/viz.html#modelly.viz.render.drawers.base.BaseSpaceDrawer)

Drawer for Voronoi diagram spaces.

Initialize the Voronoi space drawer.

**Parameters:**

**space** – The Voronoi grid space to draw

#### `draw_matplotlib(ax=None, **draw_space_kwargs)`

Draw the Voronoi diagram using matplotlib.

**Parameters:**

- **ax** – Matplotlib axes object to draw on
- ****draw_space_kwargs** – Keyword arguments passed to matplotlib’s LineCollection.

Examples

lw=2, alpha=0.5, colors=’red’

**Returns:**

The modified axes object

#### `draw_altair(chart_width=450, chart_height=350, **draw_chart_kwargs)`

Draw the Voronoi diagram using Altair.

**Parameters:**

- **chart_width** – Width for the shown chart
- **chart_height** – Height for the shown chart
- ****draw_chart_kwargs** – Additional keyword arguments for styling the chart.

Examples

- Line properties like color, strokeDash, strokeWidth, opacity.
- Other kwargs (e.g., width, title) apply to the chart.

**Returns:**

An Altair Chart object representing the Voronoi diagram.

#### `clip_line(p1, p2, box)`

Clip a line segment to a (min_x, min_y, max_x, max_y) box (Cohen-Sutherland).

Returns the clipped line segment (p1, p2) or None if it’s outside.

## Publication styles and palettes

How to use them is in [Figures and animations](https://remipelloux.github.io/Modelly/dev/figures.html).

Publication styles for Matplotlib: journal column widths and colour-blind-safe palettes.

`paper()` is a context manager that sets Matplotlib up for a figure in a journal: the figure is one or two columns wide, the fonts are small and embedded as TrueType, the colour cycle is colour-blind safe and figures are saved at print resolution:

```default
from modelly.viz import styles

with styles.paper("nature", columns=2):
    fig, ax = plt.subplots()
    ax.plot(df["Gini"])
    fig.savefig("gini.pdf")
```

The widths are those the journals’ author guides state; check the current guide before submitting. `figure_size` gives the size alone, and `rc_params` the settings as a dict.

#### `class ColumnWidths(single: float, double: float)`

A journal’s figure widths, in inches.

Create new instance of ColumnWidths(single, double)

#### `single: float`

Alias for field number 0

#### `double: float`

Alias for field number 1

#### `figure_size(journal: str = 'nature', columns: int = 1, aspect: float = 1.618033988749895) → tuple[float, float]`

The `(width, height)` in inches of a figure `columns` wide in `journal`.

**Parameters:**

- **journal** – A key of `JOURNALS`.
- **columns** – 1 for a single column, 2 for the full page width.
- **aspect** – Width divided by height; the golden ratio by default.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – For an unknown journal or a column count other than 1 or 2.

#### `paper(journal: str = 'nature', columns: int = 1, palette: str = 'okabe_ito') → Iterator[dict[str, Any]]`

Draw the figures made inside the block in a journal’s style.

**Parameters:**

- **journal** – A key of `JOURNALS`: `nature`, `science`, `pnas`, `elsevier`, `plos` or `ieee`.
- **columns** – 1 for a single column, 2 for the full page width.
- **palette** – A key of `modelly.viz.palettes.PALETTES`, the colour cycle.

**Yields:**

The settings applied, which are undone when the block ends.

#### `rc_params(journal: str = 'nature', columns: int = 1, palette: str = 'okabe_ito') → dict[str, Any]`

The Matplotlib settings `paper` applies, as a dict for `plt.rc_context`.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – For an unknown journal, palette or column count.

Colour-blind-safe palettes, as hex strings, for every backend.

`OKABE_ITO` is the eight-colour palette of Okabe and Ito, designed to stay distinct with the common forms of colour-blindness. `TOL_BRIGHT`, `TOL_VIBRANT` and `TOL_MUTED` are Paul Tol’s qualitative schemes ([https://personal.sron.nl/~pault/](https://personal.sron.nl/~pault/)), checked the same way. `PALETTES` maps their names, as `modelly.viz.styles.paper(palette=...)` takes them.

## Headless figures and animations

Draw a model’s space into a Matplotlib figure, without a GUI or a notebook.

`space_figure` is what Modelly Studio shows, what its figure export saves and what `modelly.viz.animation` turns into frames: one `SpaceRenderer` on the Matplotlib backend, drawn on a plain `Figure` (no pyplot), so it works headless on every OS.

#### `can_draw(model: Model) → bool`

Whether `model` has a space `SpaceRenderer` can draw.

#### `figure_pixels(figure: Figure) → ndarray`

The figure rendered to an `(height, width, 3)` uint8 RGB array.

#### `model_space(model: Model) → Any`

The space a model draws: `model.grid`, else `model.space`, else None.

#### `space_figure(model: Model, agent_portrayal: Callable | None = None, figsize: tuple[float, float] = (5.0, 5.0), dpi: int = 100) → Figure`

A new figure of the model’s space and agents.

**Parameters:**

- **model** – The model; its space is `model.grid` or `model.space`.
- **agent_portrayal** – Returns an `AgentPortrayalStyle` per agent; `ClassColours()` (one colour-blind-safe colour per agent class) when None.
- **figsize** – Width and height in inches.
- **dpi** – Pixels per inch.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the model has no space `SpaceRenderer` supports.

Export a space view as an animation (GIF or MP4), rendered headless.

The frames are models: the states of one run, one per frame. `frames_from_run` steps a model and yields it after every `every` steps; `frames_from_timeline` yields the model at each recorded step of a `modelly.timetravel` recording. `save_animation` draws each one as `modelly.viz.mpl.figure.space_figure` does, on one kept `_SpaceFigure` (the space’s structure is drawn once), and writes the file:

```default
from modelly.viz.animation import frames_from_run, save_animation

save_animation(frames_from_run(model, steps=100), "run.mp4")
```

GIF needs only Pillow (a Matplotlib dependency). MP4 needs the `video` extra (`pip install modelly-abm[video]`), whose `imageio-ffmpeg` ships an ffmpeg binary for Windows, macOS and Linux: nothing to install system-wide.

#### `class AnimationOptions(fps: int = 10, figsize: tuple[float, float] = (5.0, 5.0), dpi: int = 100, loop: bool = True)`

How an animation is drawn and timed.

**Variables:**

- **fps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Frames per second.
- **figsize** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*float*](https://docs.python.org/3/builtins/functions.html#float)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – Width and height of each frame, in inches.
- **dpi** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Pixels per inch.
- **loop** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – For GIF, play in a loop (MP4 players decide for themselves).

#### `frames_from_run(model: Model, steps: int, every: int = 1) → Iterator[Model]`

Yield `model` now, then after every `every` steps, `steps` steps in all.

The model is stepped in place; the run stops early when `model.running` is False.

#### `frames_from_timeline(timeline: Timeline) → Iterator[Model]`

Yield the model at each recorded step of `timeline`, oldest first.

#### `save_animation(models: Iterable[Model], path: str | Path, options: AnimationOptions | None = None, agent_portrayal: Callable | None = None) → int`

Draw each model’s space as one frame and write a GIF or MP4 to `path`.

**Parameters:**

- **models** – The frames, such as `frames_from_run(...)` or `frames_from_timeline(...)`.
- **path** – The file; its suffix, `.gif` or `.mp4`, picks the format.
- **options** – Frame rate, frame size and looping.
- **agent_portrayal** – As for `space_figure`; one colour per agent class by default.

**Returns:**

The number of frames written.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – For a suffix other than `.gif` and `.mp4`.
