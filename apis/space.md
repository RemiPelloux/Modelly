# Space

`modelly.space` holds the discrete cell spaces (grids, networks, Voronoi meshes), continuous space, property layers and the integer cell index. The names most models need are exported by the package itself: `from modelly.space import OrthogonalMooreGrid, CellAgent`.

Module

Contents

modelly.space.cells

Cell, CellCollection, the cell agents, CellIndex, Occupancy

modelly.space.base

DiscreteSpace, the base of every discrete space

modelly.space.grid

Grid, OrthogonalMooreGrid, OrthogonalVonNeumannGrid, HexGrid, property layers

modelly.space.network

Network

modelly.space.voronoi, modelly.space.delaunay

VoronoiGrid and the triangulation behind it

modelly.space.continuous

ContinuousSpace, ContinuousSpaceAgent, vectorised helpers

## Cells

`Cell` takes its neighbourhood methods (`neighborhood`, `get_neighborhood`) from `modelly.space.cells.neighborhood`; they are listed under `Cell`.

Cells are positions in space that can have properties and contain agents.

A cell represents a location that can: - Have properties (like temperature or resources) - Track and limit the agents it contains - Connect to neighboring cells - Provide neighborhood information

Cells form the foundation of the cell space system, enabling rich spatial environments where both location properties and agent behaviors matter. They’re useful for modeling things like varying terrain, infrastructure capacity, or environmental conditions.

#### `class Cell(coordinate: tuple[int, ...], position: ndarray | None = None, capacity: int | None = None, random: Random | None = None)`

The cell represents a position in a discrete space.

**Variables:**

- **coordinate** (*Coordinate*) – the logical position(or index) of the cell in the discrete space
- **position** (*np.ndarray** | **None*) – the physical position of the cell in the discrete space
- **agents** (*List**[*[*Agent*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent)*]*) – the agents occupying the cell
- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the maximum number of agents that can simultaneously occupy the cell
- **random** (*Random*) – the random number generator

Notes

Neighborhoods are cached per cell, keyed on `(radius, include_center)`. The cache belongs to the cell (not to the class), so discarding a space frees its cells, and changing one cell’s connections only invalidates that cell’s own neighborhoods.

Initialise the cell.

**Parameters:**

- **coordinate** – coordinates of the cell
- **position** – physical coordinates of the cell
- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the capacity of the cell. If None, the capacity is infinite
- **random** (*Random*) – the random number generator to use

#### `property position: ndarray`

Get the physical position of the cell.

**Returns:**

Physical position of the cell

**Return type:**

np.ndarray

#### `connect(other: Cell, key: tuple[int, ...] | None = None) → None`

Connects this cell to another cell.

**Parameters:**

- **other** ([*Cell*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)) – other cell to connect to
- **key** (*Tuple**[*[*int*](https://docs.python.org/3/builtins/functions.html#int)*, **...**]*) – key for the connection. Should resemble a relative coordinate

#### `disconnect(other: Cell) → None`

Disconnects this cell from another cell.

**Parameters:**

**other** ([*Cell*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)) – other cell to remove from connections

#### `add_agent(agent: CellAgent) → None`

Adds an agent to the cell.

**Parameters:**

**agent** ([*CellAgent*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.CellAgent)) – agent to add to this Cell

#### `remove_agent(agent: CellAgent) → None`

Removes an agent from the cell.

**Parameters:**

**agent** ([*CellAgent*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.CellAgent)) – agent to remove from this cell

#### `property is_empty: bool`

Returns a bool of the contents of a cell.

#### `property is_full: bool`

Returns a bool of the contents of a cell.

#### `property agents: list[CellAgent]`

Returns a list of the agents occupying the cell.

#### `get_neighborhood(radius: int = 1, include_center: bool = False) → CellCollection[Cell]`

Returns a CellCollection of all neighboring cells for the given radius.

For getting the direct neighborhood (i.e., radius=1) you can also use the neighborhood property.

**Parameters:**

- **radius** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the radius of the neighborhood
- **include_center** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – include the center of the neighborhood

**Returns:**

a CellCollection of all neighboring cells

#### `property neighborhood: CellCollection[Cell]`

Returns the direct neighborhood of the cell.

This is equivalent to cell.get_neighborhood(radius=1)

Collection class for managing and querying groups of cells.

The CellCollection class provides a consistent interface for operating on multiple cells, supporting: - Filtering and selecting cells based on conditions - Random cell and agent selection - Access to contained agents - Group operations

This is useful for implementing area effects, zones, or any operation that needs to work with multiple cells as a unit. The collection handles efficient iteration and agent access across cells. The class is used throughout the cell space implementation to represent neighborhoods, selections, and other cell groupings.

#### `class CellCollection(cells: Mapping[T, list[CellAgent]] | Iterable[T], random: Random | None = None)`

An immutable collection of cells.

**Variables:**

- **cells** (*List**[*[*Cell*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)*]*) – The list of cells this collection represents
- **agents** (*List**[*[*CellAgent*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.CellAgent)*]*) – List of agents occupying the cells in this collection
- **random** (*Random*) – The random number generator

Notes

With random=None the collection takes the generator of its first cell that has one, else the model generator of its first agent. A UserWarning is issued only when there is neither; pass random=self.random from a Model or Agent to avoid it.

Initialize a CellCollection.

**Parameters:**

- **cells** – cells to add to the collection
- **random** – a seeded random number generator; None takes the cells’ or their agents’ model generator.

#### `property empties: CellCollection[T]`

The cells of this collection that hold no agent, as a new collection.

Reads the live occupancy lists directly, so it costs one truth test per cell rather than a property call per cell.

#### `select_random_cell(default=<object object>) → T | None`

Select a random cell from the collection.

**Parameters:**

**default** – Value to return if the collection is empty. If not provided, raises LookupError.

**Returns:**

A random cell, or the default value if provided and collection is empty.

**Return type:**

T

**Raises:**

[**LookupError**](https://docs.python.org/3/builtins/exceptions.html#LookupError) – If collection is empty and no default is provided.

#### `select_random_agent(default=<object object>) → CellAgent | None`

Select a random agent from the collection.

**Parameters:**

**default** – Value to return if the collection is empty. If not provided, raises LookupError.

**Returns:**

A random agent, or the default value if provided and collection is empty.

**Return type:**

[CellAgent](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.CellAgent)

**Raises:**

[**LookupError**](https://docs.python.org/3/builtins/exceptions.html#LookupError) – If collection is empty and no default is provided.

#### `select(filter_func: Callable[[T], bool] | None = None, at_most: int | float = inf)`

Select cells based on filter function.

**Parameters:**

- **filter_func** – filter function
- **at_most** – The maximum amount of cells to select. Defaults to infinity. - If an integer, at most the first number of matching cells is selected. - If a float between 0 and 1, at most that fraction of original number of cells

**Returns:**

CellCollection

**Raises:**

- [**TypeError**](https://docs.python.org/3/builtins/exceptions.html#TypeError) – If at_most is not an integer or float, or is a boolean.
- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If at_most is a negative integer, or a float not in the range (0.0, 1.0].

## Cell agents

Agents that understand how to exist in and move through cell spaces.

Provides specialized agent classes that handle cell occupation, movement, and proper registration: - CellAgent: Mobile agents that can move between cells - FixedAgent: Immobile agents permanently fixed to cells - Grid2DMovingAgent: Agents with grid-specific movement capabilities

These classes ensure consistent agent-cell relationships and proper state management as agents move through the space. They can be used directly or as examples for creating custom cell-aware agents.

#### `class HasCellProtocol(*args, **kwargs)`

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

Protocol for discrete space cell holders.

#### `class HasCell`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Descriptor for cell movement behavior.

#### `property cell: Cell | None`

The cell the agent is in.

#### `class BasicMovement`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Mixin for moving agents in discrete space.

#### `move_to(cell: Cell) → None`

Move to a new cell.

#### `move_relative(direction: tuple[int, ...])`

Move to a cell relative to the current cell.

**Parameters:**

**direction** – The direction to move in.

#### `class FixedCell`

Bases: [`HasCell`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.HasCell)

Mixin for agents that are fixed to a cell.

Once assigned to a cell, the agent cannot be moved to a different cell. The assignment is atomic: if cell.add_agent() raises (e.g. capacity reached), the agent’s _modelly_cell reference is left unchanged.

#### `property cell: Cell | None`

The cell the agent is fixed to.

#### `class CellAgent(model: M, *args, **kwargs)`

Bases: [`Agent`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent), [`HasCell`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.HasCell), [`BasicMovement`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.BasicMovement)

Cell Agent is an extension of the Agent class and adds behavior for moving in discrete spaces.

**Variables:**

**cell** ([*Cell*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)) – The cell the agent is currently in.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `remove()`

Remove the agent from the model.

#### `class FixedAgent(model: M, *args, **kwargs)`

Bases: [`Agent`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent), [`FixedCell`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.FixedCell)

A patch in a 2D grid.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `remove()`

Remove the agent from the model.

**Raises:**

[**AgentRemovedError**](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.exceptions.AgentRemovedError) – when the agent has no cell: removed already, or never placed.

#### `class Grid2DMovingAgent(model: M, *args, **kwargs)`

Bases: [`CellAgent`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.CellAgent)

Mixin for moving agents in 2D grids.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `move(direction: str, distance: int = 1)`

Move the agent in a cardinal direction.

**Parameters:**

- **direction** – The cardinal direction to move in.
- **distance** – The distance to move.

#### `class HexGridMovingAgent(model: M, *args, **kwargs)`

Bases: [`CellAgent`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.agents.CellAgent)

A specialized agent for moving on a HexGrid (Even-R / Pointy-Topped).

This agent correctly handles the alternating connectivity of the HexGrid defined in modelly.space.grid.grids, where the Row Index (y) determines parity.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `move(direction: str, distance: int = 1) → None`

Move the agent in a hex direction respecting row parity.

**Parameters:**

- **direction** – One of ‘nw’, ‘ne’, ‘sw’, ‘se’, ‘w’, ‘e’ (or aliases which are ‘n’ and ‘s’).
- **distance** – Number of steps to take.

## Discrete spaces

Abstract Base class for building cell-based spatial environments.

DiscreteSpace provides the core functionality needed by all cell-based spaces: - Cell creation and tracking - Agent-cell relationship management - Property Layer support - Random selection capabilities - Capacity management

This serves as the foundation for specific space implementations like grids and networks, ensuring consistent behavior and shared functionality across different space types. All concrete cell space implementations (grids, networks, etc.) inherit from this class.

#### `space_agents(space: DiscreteSpace) → Iterator[CellAgent]`

The agents in the cells’ lists, then those a CellIndex tracks by row column.

#### `class DiscreteSpace(capacity: int | None = None, cell_klass: type[T] = <class 'modelly.space.cells.cell.Cell'>, random: Random | None = None)`

Base class for all discrete spaces.

**Variables:**

- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – The capacity of the cells in the discrete space
- **all_cells** ([*CellCollection*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.collection.CellCollection)) – The cells composing the discrete space
- **random** (*Random*) – The random number generator
- **cell_klass** (*Type*) – the type of cell class
- **empties** ([*CellCollection*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.collection.CellCollection)) – collection of all cells that are empty
- **property_layers** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **np.ndarray**]*) – property_layer of the discrete space

Notes

A UserWarning is issued if random=None. You can resolve this warning by explicitly passing a random number generator. In most cases, this will be the seeded random number generator in the model. So, you would do random=self.random in a Model or Agent instance.

Instantiate a DiscreteSpace.

**Parameters:**

- **capacity** – capacity of cells
- **cell_klass** – base class for all cells
- **random** – random number generator

#### `property agents: AgentSet`

Return an AgentSet with the agents in the space, row-placed ones included.

#### `abstractmethod find_nearest_cell(position: ndarray) → T`

Find the cell at or nearest to the given position.

#### `add_cell(cell: T)`

Add a cell to the space.

**Parameters:**

**cell** – cell to add

Note

Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared correctly if you are adding or removing cells and connections at runtime.

Warning

Coordinate Collision: If a cell already exists at the specified coordinates (e.g., cell1), it will be overwritten silently by the new cell (cell2).

Ensure the target coordinates are vacant before calling this method.

#### `remove_cell(cell: T)`

Remove a cell from the space.

Note

Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared correctly if you are adding or removing cells and connections at runtime.

#### `add_connection(cell1: T, cell2: T)`

Add a connection between the two cells.

Note

Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared correctly if you are adding or removing cells and connections at runtime.

#### `remove_connection(cell1: T, cell2: T)`

Remove a connection between the two cells.

Note

Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared correctly if you are adding or removing cells and connections at runtime.

#### `property all_cells`

Return all cells in space.

#### `property empties: CellCollection[T]`

Return all empty in spaces.

#### `select_random_empty_cell() → T`

Select a random empty cell.

Sparse spaces are answered by a few random draws. The first time the draws all fail (or when `_try_random` is False) the space builds an index of its empty cells, kept current by `cell.empty` from then on, so every later call is O(1) regardless of how full the space is.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the space has no empty cell.

### Grids

The base class shared by every grid, plus its empty-cell index.

Concrete connection patterns (Moore, Von Neumann, hexagonal) live in [`modelly.space.grid.grids`](https://remipelloux.github.io/Modelly/apis/space.html#module-modelly.space.grid.grids).

#### `class Grid(dimensions: ~collections.abc.Sequence[int], torus: bool = False, capacity: float | None = None, random: ~random.Random | None = None, cell_klass: type[~modelly.space.grid.base.T] = <class 'modelly.space.cells.cell.Cell'>)`

Bases: [`HasPropertyLayers`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.grid.layers.HasPropertyLayers), [`DiscreteSpace`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.base.DiscreteSpace)[`T`]

Base class for all grid classes.

**Variables:**

- **dimensions** (*Sequence**[*[*int*](https://docs.python.org/3/builtins/functions.html#int)*]*) – the dimensions of the grid
- **torus** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – whether the grid is a torus
- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the capacity of a grid cell
- **random** (*Random*) – the random number generator
- **_try_random** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – whether to get empty cell be repeatedly trying random cell

Notes

width and height are accessible via property_layers, higher dimensions can be retrieved via dimensions

Initialise the grid class.

**Parameters:**

- **dimensions** – the dimensions of the space
- **torus** – whether the space wraps
- **capacity** – capacity of the grid cell
- **random** – a random number generator
- **cell_klass** – the base class to use for the cells

#### `property width: int`

Convenience access to the width of the grid.

#### `property height: int`

Convenience access to the height of the grid.

#### `get_neighborhood_mask(coordinate, include_center: bool = True, radius: int = 1) → ndarray`

Return a boolean mask shaped like `self.dimensions` for a neighborhood.

#### `find_nearest_cell(position: ndarray) → T`

Find the cell containing the given position.

**Parameters:**

**position** – Physical position [x, y]

**Returns:**

The cell containing the position

**Return type:**

[Cell](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If position is outside grid bounds and not a torus

#### `property cells_with_capacity: CellCollection[T]`

Return all cells that have available capacity (i.e. are not full).

A cell is considered *available* if `not cell.is_full`.

This is meaningfully different from `empties`: `empties` only includes cells with **zero** agents. If a cell has `capacity=5` and currently holds 3 agents it is **not** empty, but it **is** still available. `cells_with_capacity` is therefore the correct API for models where agents share cells up to a finite limit.

For cells with `capacity=None` (unlimited), every cell is always available regardless of how many agents it holds.

**Returns:**

All cells where `len(agents) < capacity` (or all cells when capacity is None).

**Return type:**

[CellCollection](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.collection.CellCollection)[T]

Example:

```default
# Place an agent in any non-full cell
agent.move_to(grid.select_random_cell_with_capacity())

# Count how many cells still have room
len(list(grid.cells_with_capacity))
```

#### `select_random_cell_with_capacity() → Cell`

Select a random cell that has remaining capacity.

**Raises:**

[**IndexError**](https://docs.python.org/3/builtins/exceptions.html#IndexError) – If every cell in the grid is at full capacity.

Example:

```default
# Safe placement that respects capacity limits
free_cell = grid.select_random_cell_with_capacity()
agent.move_to(free_cell)
```

Grid-based cell space implementations with different connection patterns.

Provides several grid types for organizing cells: - OrthogonalMooreGrid: 8 neighbors in 2D, (3^n)-1 in nD - OrthogonalVonNeumannGrid: 4 neighbors in 2D, 2n in nD - HexGrid: 6 neighbors in hexagonal pattern (2D only)

Each grid type supports optional wrapping (torus) and cell capacity limits. Choose based on how movement and connectivity should work in your model - Moore for unrestricted movement, Von Neumann for orthogonal-only movement, or Hex for more uniform distances.

The shared machinery (cell creation, property layers, empty-cell selection, pickling) lives in [`modelly.space.grid.base`](https://remipelloux.github.io/Modelly/apis/space.html#module-modelly.space.grid.base); `Grid` is re-exported here so `from modelly.space.grid.grids import Grid` keeps working.

#### `class Grid(dimensions: ~collections.abc.Sequence[int], torus: bool = False, capacity: float | None = None, random: ~random.Random | None = None, cell_klass: type[~modelly.space.grid.base.T] = <class 'modelly.space.cells.cell.Cell'>)`

Bases: [`HasPropertyLayers`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.grid.layers.HasPropertyLayers), [`DiscreteSpace`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.base.DiscreteSpace)[`T`]

Base class for all grid classes.

**Variables:**

- **dimensions** (*Sequence**[*[*int*](https://docs.python.org/3/builtins/functions.html#int)*]*) – the dimensions of the grid
- **torus** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – whether the grid is a torus
- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the capacity of a grid cell
- **random** (*Random*) – the random number generator
- **_try_random** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – whether to get empty cell be repeatedly trying random cell

Notes

width and height are accessible via property_layers, higher dimensions can be retrieved via dimensions

Initialise the grid class.

**Parameters:**

- **dimensions** – the dimensions of the space
- **torus** – whether the space wraps
- **capacity** – capacity of the grid cell
- **random** – a random number generator
- **cell_klass** – the base class to use for the cells

#### `property width: int`

Convenience access to the width of the grid.

#### `property height: int`

Convenience access to the height of the grid.

#### `get_neighborhood_mask(coordinate, include_center: bool = True, radius: int = 1) → ndarray`

Return a boolean mask shaped like `self.dimensions` for a neighborhood.

#### `find_nearest_cell(position: ndarray) → T`

Find the cell containing the given position.

**Parameters:**

**position** – Physical position [x, y]

**Returns:**

The cell containing the position

**Return type:**

[Cell](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If position is outside grid bounds and not a torus

#### `property cells_with_capacity: CellCollection[T]`

Return all cells that have available capacity (i.e. are not full).

A cell is considered *available* if `not cell.is_full`.

This is meaningfully different from `empties`: `empties` only includes cells with **zero** agents. If a cell has `capacity=5` and currently holds 3 agents it is **not** empty, but it **is** still available. `cells_with_capacity` is therefore the correct API for models where agents share cells up to a finite limit.

For cells with `capacity=None` (unlimited), every cell is always available regardless of how many agents it holds.

**Returns:**

All cells where `len(agents) < capacity` (or all cells when capacity is None).

**Return type:**

[CellCollection](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.collection.CellCollection)[T]

Example:

```default
# Place an agent in any non-full cell
agent.move_to(grid.select_random_cell_with_capacity())

# Count how many cells still have room
len(list(grid.cells_with_capacity))
```

#### `select_random_cell_with_capacity() → Cell`

Select a random cell that has remaining capacity.

**Raises:**

[**IndexError**](https://docs.python.org/3/builtins/exceptions.html#IndexError) – If every cell in the grid is at full capacity.

Example:

```default
# Safe placement that respects capacity limits
free_cell = grid.select_random_cell_with_capacity()
agent.move_to(free_cell)
```

#### `class HexGrid(dimensions: ~collections.abc.Sequence[int], torus: bool = False, capacity: float | None = None, random: ~random.Random | None = None, cell_klass: type[~modelly.space.grid.grids.T] = <class 'modelly.space.cells.cell.Cell'>)`

Bases: [`Grid`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.grid.base.Grid)[`T`]

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

#### `class OrthogonalMooreGrid(dimensions: ~collections.abc.Sequence[int], torus: bool = False, capacity: float | None = None, random: ~random.Random | None = None, cell_klass: type[~modelly.space.grid.base.T] = <class 'modelly.space.cells.cell.Cell'>)`

Bases: [`Grid`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.grid.base.Grid)[`T`]

Grid where cells are connected to their 8 neighbors.

Example for two dimensions:

```default
directions = [
    (-1, -1), (-1, 0), (-1, 1),
    ( 0, -1),          ( 0, 1),
    ( 1, -1), ( 1, 0), ( 1, 1),
]
```

Initialise the grid class.

**Parameters:**

- **dimensions** – the dimensions of the space
- **torus** – whether the space wraps
- **capacity** – capacity of the grid cell
- **random** – a random number generator
- **cell_klass** – the base class to use for the cells

#### `class OrthogonalVonNeumannGrid(dimensions: ~collections.abc.Sequence[int], torus: bool = False, capacity: float | None = None, random: ~random.Random | None = None, cell_klass: type[~modelly.space.grid.base.T] = <class 'modelly.space.cells.cell.Cell'>)`

Bases: [`Grid`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.grid.base.Grid)[`T`]

Grid where cells are connected to their 4 neighbors.

Example for two dimensions:

```default
directions = [
            (0, -1),
    (-1, 0),         ( 1, 0),
            (0,  1),
]
```

Initialise the grid class.

**Parameters:**

- **dimensions** – the dimensions of the space
- **torus** – whether the space wraps
- **capacity** – capacity of the grid cell
- **random** – a random number generator
- **cell_klass** – the base class to use for the cells

#### `pickle_gridcell(obj)`

Helper function for pickling GridCell instances.

#### `unpickle_gridcell(parent, fields)`

Helper function for unpickling GridCell instances.

### Property layers

Grids take `create_property_layer`, `add_property_layer` and `remove_property_layer` from this mixin.

Property layers: numpy arrays attached to a grid and exposed on its cells.

A property layer is one `np.ndarray` shaped like the grid. The grid exposes it as an attribute (`grid.sugar`) and every cell of that grid gets an accessor (`cell.sugar`) that reads and writes the array at the cell’s coordinate, so vectorised updates on the array and per-cell reads stay in sync for free.

#### `class HasPropertyLayers`

Mixin giving a grid named property layers backed by numpy arrays.

Expects the host to define `dimensions` (the array shape), `cell_klass` (a class private to the grid, since accessors are installed on it), `property_layers` and `_read_only_layers`.

#### `create_property_layer(name: str, default_value=0.0, dtype=<class 'float'>, read_only: bool = False) → ndarray`

Create a property layer array and attach it to cells.

Warning: Do not reassign grid.name directly — this will detach it from property_layers and break cell-level access. Use in-place operations.

grid.sugar[:] = 0 # correct grid.sugar = array # wrong — breaks cell access

#### `add_property_layer(name: str, array: ndarray, read_only: bool = False) → None`

Attach an existing array as a property layer. Shape must match self.dimensions.

Warning: Do not reassign grid.name directly — this will detach it from property_layers and break cell-level access. Use in-place operations.

grid.sugar[:] = 0 # correct grid.sugar = array # wrong — breaks cell access

#### `remove_property_layer(name: str) → None`

Remove a property_layer and its grid and cell attributes.

**Parameters:**

**name** – property_layer name.

### Network

Network-based cell space using arbitrary connection patterns.

Creates spaces where cells connect based on network relationships rather than spatial proximity. Built on NetworkX graphs, this enables: - Arbitrary connectivity patterns between cells - Graph-based neighborhood definitions - Logical rather than physical distances - Dynamic connectivity changes - Integration with NetworkX’s graph algorithms

Useful for modeling systems like social networks, transportation systems, or any environment where connectivity matters more than physical location.

#### `class Network(G: Any, capacity: int | None = None, random: Random | None = None, cell_klass: type[Cell] = <class 'modelly.space.cells.cell.Cell'>, layout: Mapping | Callable | None = None)`

Bases: [`DiscreteSpace`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.base.DiscreteSpace)[[`Cell`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)]

A networked discrete space.

A Networked grid.

**Parameters:**

- **G** – a NetworkX Graph instance.
- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the capacity of the cell
- **random** (*Random*) – a random number generator
- **cell_klass** ([*type*](https://docs.python.org/3/builtins/functions.html#type)*[*[*Cell*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)*]*) – The base Cell class to use in the Network
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

[Cell](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)

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

### Voronoi

Cell spaces based on Voronoi tessellation around seed points.

Creates irregular spatial divisions by building cells around seed points, where each cell contains the area closer to its seed than any other. Features: - Organic-looking spaces from point sets - Automatic neighbor determination - Area-based cell capacities - Natural regional divisions

Useful for models requiring irregular but mathematically meaningful spatial divisions, like territories, service areas, or natural regions.

#### `class VoronoiGrid(centroids_coordinates: ~collections.abc.Sequence[~collections.abc.Sequence[float]], capacity: int | ~collections.abc.Callable | None = None, random: ~random.Random | None = None, cell_klass: type[~modelly.space.cells.cell.Cell] = <class 'modelly.space.cells.cell.Cell'>)`

Bases: [`DiscreteSpace`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.base.DiscreteSpace)

Voronoi meshed GridSpace.

A Voronoi Tessellation Grid.

Given a set of points, this class creates a grid where a cell is centered in each point, its neighbors are given by Voronoi Tessellation cells neighbors and the capacity by the polygon area.

**Parameters:**

- **centroids_coordinates** – coordinates of centroids to build the tessellation space
- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)* | **Callable*) – capacity of the cells in the discrete space, or a callable computing the (int) capacity of a cell from its (float) polygon area
- **random** (*Random*) – random number generator
- **cell_klass** ([*type*](https://docs.python.org/3/builtins/functions.html#type)*[*[*Cell*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)*]*) – type of cell class

#### `find_nearest_cell(position: ndarray) → Cell`

Find the Voronoi cell nearest to the given position.

**Parameters:**

**position** – Physical position [x, y]

**Returns:**

The Voronoi cell whose centroid is nearest to position

**Return type:**

[Cell](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.cell.Cell)

A 2D Delaunay triangulation (Bowyer-Watson), the basis of the Voronoi grid.

#### `class Delaunay(center: tuple = (0, 0), radius: int = 9999)`

Class to compute a Delaunay triangulation in 2D.

ref: [jmespadero/pyDelaunay2D](http://github.com/jmespadero/pyDelaunay2D)

Init and create a new frame to contain the triangulation.

**Parameters:**

- **center** – Optional position for the center of the frame. Default (0,0)
- **radius** – Optional distance from corners to the center.

#### `add_point(point: Sequence) → None`

Add a point to the current DT, and refine it using Bowyer-Watson.

#### `export_triangles() → list`

Export the current list of Delaunay triangles.

#### `export_voronoi_regions()`

Export coordinates and regions of Voronoi diagram as indexed data.

## Integer cells: index, occupancy and row-placed agents

Integer rows for the cells of a discrete space, and sparse operators over them.

Every discrete space (grid, network, Voronoi mesh) is a set of cells joined by `connections`. Numbering the cells gives each one a row, and the connections become a sparse adjacency matrix. Whole-population questions then cost one numpy call each instead of one Python loop per agent:

- `counts(rows)`: how many agents, or how much of a quantity, sit in each cell;
- `neighbor_sum(values)`: for every cell, the sum of `values` over its neighbours;
- `random_neighbor(rows)`: one uniformly chosen neighbour for every row.

Agents that declare a `Column` for their cell row (`row = Column(np.intp)`, kept current with `self.row = cell.index` when they move) can combine these with `ColumnTable.draw` into a vectorised step phase. See `docs/vectorised_phases.md` for the equivalence arguments.

#### `class CellIndex(space: DiscreteSpace)`

Rows for the cells of `space` and the sparse adjacency between them.

Building the index writes `cell.index` on every cell, in the order of `space.all_cells`. For grids that order is the C order of the coordinates, so a per-cell vector reshaped to the grid’s dimensions is a property layer.

Number the cells of `space`; the adjacency is built on first use.

#### `track(model: Model, agent_class: type, column: str = 'row') → None`

Declare that `agent_class` keeps its cell as a row `column`.

Such agents are in no cell’s agent list; tracking them makes the space list them (`space.agents`) and lets the visualisation place them at `index.cells[agent.<column>]`.

#### `tracked_agents() → Iterator[Agent]`

The live agents of every tracked class, in table order.

#### `cell_of(agent: Agent) → Cell`

The cell a tracked agent occupies, from its row column.

#### `rows(cells: Iterable[Cell]) → np.ndarray`

Return the row of each cell in `cells`.

#### `counts(rows: ndarray, weights: ndarray | None = None) → ndarray`

Per-cell total of `weights` (or of ones) over the agents sitting in `rows`.

#### `property adjacency: csr_matrix`

The cell adjacency as a CSR matrix with one entry per connection.

#### `neighbor_sum(values: ndarray) → ndarray`

For every cell, the sum of `values` over its neighbouring cells.

#### `random_neighbor(rows: ndarray, rng: Generator) → ndarray`

One uniformly chosen neighbour row per entry of `rows`.

A row without neighbours is returned unchanged.

#### `to_layer(values: ndarray) → ndarray`

Reshape a per-cell vector to the grid’s dimensions (a property layer view).

Who sits in which cell, from a row column, without per-cell agent lists.

Agents that keep their cell as a `Column` of rows (see `CellIndex`) move by assigning the column; nothing else has to be updated. When a step needs to know who shares a cell, `Occupancy` sorts the rows once (O(n log n)) and answers per-cell questions from the sorted order. `claim` is the vectorised form of “each claimant takes one of the members of its cell, if any is left”: it has the law of the sequential version in which the claimants act in a uniformly random order (see docs/vectorised_phases.md).

#### `class Occupancy(rows: ndarray, n_cells: int)`

The agents of a table grouped by cell row, rebuilt from the row column.

Sort the agents (their table indices) by the cell row they occupy.

#### `counts() → ndarray`

How many agents sit in each cell.

#### `bounds(cells: ndarray) → tuple[ndarray, ndarray]`

The `[start, end)` slice of `order` holding the members of each cell.

#### `members(cell: int) → ndarray`

The table indices of the agents in `cell`.

#### `random_member(cells: ndarray, rng: Generator) → ndarray`

One uniformly chosen member of each cell in `cells`, or `NO_MATCH` if empty.

#### `claim(occupancy: Occupancy, cells: ndarray, rng: Generator) → ndarray`

For each claimant, one distinct member of its cell, or `NO_MATCH`.

`cells[k]` is the cell of claimant `k`. The matching has the law of the sequential rule “claimants act in a uniformly random order and each takes a uniformly random member of its cell not yet taken”: every cell ends up with min(claimants, members) matches, a uniform random subset of its members is taken and a uniform random subset of its claimants is served. Each round, every unserved claimant draws a member of its cell; draws of already taken members are rejected, collisions go to a random priority, and the losers draw again while their cell still has a free member.

## Continuous space

`ContinuousSpace` takes its neighbour queries (`get_agents_in_radius`, `neighbors_within`, `get_k_nearest_agents`) from `modelly.space.continuous.queries`; they are listed under `ContinuousSpace`.

A Continuous Space class.

#### `class ContinuousSpace(dimensions: ArrayLike, torus: bool = False, random: Random | None = None, n_agents: int = 100)`

Continuous space where each agent can have an arbitrary position.

Create a new continuous space.

**Parameters:**

- **dimensions** – a numpy array like object where each row specifies the minimum and maximum value of that dimension.
- **torus** – boolean for whether the space wraps around or not
- **random** – a seeded stdlib random.Random instance
- **n_agents** – the expected number of agents in the space

Internally, a numpy array is used to store the positions of all agents. This is resized if needed, but you can control the initial size explicitly by passing n_agents.

#### `property dimensions: ndarray`

The `(ndims, 2)` array of each dimension’s minimum and maximum (read-only).

#### `property agents: AgentSet[A]`

Return an AgentSet with the agents in the space.

#### `calculate_difference_vector(point: ndarray, agents=None) → ndarray`

Calculate the difference vector between the point and all agenents.

**Parameters:**

- **point** – the point to calculate the difference vector for
- **agents** – the agents to calculate the difference vector of point with. By default, all agents are considered.

#### `calculate_distances(point: ArrayLike, agents: Iterable[Agent] | None = None, **kwargs) → tuple[ndarray, list]`

Calculate the distance between the point and all agents.

**Parameters:**

- **point** – the point to calculate the difference vector for
- **agents** – the agents to calculate the difference vector of point with. By default, all agents are considered.
- **kwargs** – any additional keyword arguments are passed to scipy’s cdist, which is used only if torus is False. This allows for non-Euclidian distance measures.

#### `get_agents_in_radius(point: ArrayLike, radius: float | int = 1) → tuple[list, ndarray]`

Return the agents and their distances within a radius for the point.

#### `get_k_nearest_agents(point: ArrayLike, k: int = 1) → tuple[list, ndarray]`

Return the k nearest agents and their distances to the point.

Notes

This method returns exactly k agents, ignoring ties. In case of ties, the earlier an agent is inserted the higher it will rank.

If fewer than k agents are present in the space, all agents are returned and a UserWarning is emitted to indicate that the requested k could not be satisfied. If the space is empty or k <= 0, an empty result is returned without a warning.

#### `in_bounds(point: ArrayLike) → bool`

Check if point is inside the bounds of the space.

#### `neighbors_within(radius: float | int) → dict[Agent, list[Agent]]`

Return, for every agent, the other agents within `radius` of it.

One KD-tree is built from the positions as they are now and queried for the whole population in a single call, which is O(n log n) instead of the O(n²) of asking each agent in turn. On a torus the tree is periodic, so neighbours across the wrap are found. Use it at the start of a step for a simultaneous update: every agent then sees the same snapshot of positions.

The result is cached on the positions’ content, so asking again before any agent moves costs a hash of the position array instead of a new tree.

**Returns:**

dict mapping each agent to a list of its neighbours (itself excluded).

#### `torus_correct(point: ArrayLike) → ndarray`

Apply a torus correction to the point.

Continuous space agents.

#### `class HasPositionProtocol(*args, **kwargs)`

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

Protocol for continuous space position holders.

#### `class ContinuousSpaceAgent(space: ContinuousSpace, model)`

Bases: [`Agent`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent)

A continuous space agent.

**Variables:**

- **space** ([*ContinuousSpace*](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.continuous.space.ContinuousSpace)) – the continuous space in which the agent is located
- **position** (*np.ndarray*) – the position of the agent

Initialize a continuous space agent.

**Parameters:**

- **space** – the continuous space in which the agent is located
- **model** – the model to which the agent belongs

#### `property position: ndarray`

Position of the agent.

#### `remove() → None`

Remove and delete the agent from the model and continuous space.

**Raises:**

[**AgentRemovedError**](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.exceptions.AgentRemovedError) – when the agent was already removed.

#### `get_neighbors_in_radius(radius: float | int = 1) → tuple[list[ContinuousSpaceAgent], ndarray]`

Get neighbors within radius.

**Parameters:**

**radius** – radius within which to look for neighbors

#### `get_nearest_neighbors(k: int = 1) → tuple[list[ContinuousSpaceAgent], ndarray]`

Get neighbors within radius.

**Parameters:**

**k** – the number of nearest neighbors to return

Whole-population operations on a continuous space.

`neighbors_within` on the space answers “who is near whom” with one KD-tree. The two helpers here complete the vectorised step: `pairs_within` returns the same neighbour relation as index pairs, ready for `np.add.at` or `bincount` aggregation, and `move_all` writes every agent’s new position in one call.

#### `pairs_within(space: ContinuousSpace, radius: float) → tuple[np.ndarray, np.ndarray]`

Every unordered pair of agents within `radius`, as two row arrays `(i, j)`.

Rows index `space.agent_positions` and `space.active_agents`; `i < j` and each pair appears once. On a torus the tree is periodic.

#### `difference_vectors(space: ContinuousSpace, i: np.ndarray, j: np.ndarray) → np.ndarray`

The vector from agent `i` to agent `j` for each pair, torus-corrected.

#### `move_all(space: ContinuousSpace, positions: np.ndarray) → None`

Set every agent’s position at once; wraps on a torus, clips otherwise.
