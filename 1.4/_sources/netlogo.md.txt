# From NetLogo

`python -m modelly.netlogo` (or `modelly netlogo`) translates a NetLogo model, a `.nlogo` file,
into a Python module you can run, test and lint like any Modelly model. It reads a well-defined
subset of NetLogo, listed below. Anything outside that subset stays in the output as a
`# NETLOGO` comment, and the report lists it with its line number. Nothing is dropped without
being listed.

```bash
python -m modelly.netlogo fire.nlogo -o fire.py      # translate a model to a file
python -m modelly.netlogo model.nlogo                # print the Python on stdout
python -m modelly.netlogo --example wolf_sheep -o wolf_sheep.py   # a bundled model
python -m modelly.netlogo --example fire --show      # print the bundled NetLogo source
```

```python
from fire import FireModel, FireScenario

model = FireModel(FireScenario(rng=1, density=62))
while model.running:
    model.step()
print(model.burned_trees / model.initial_trees)
print(model.datacollector.get_model_vars_dataframe().tail())
```

The translated model's `setup` runs when the model is created, and `step()` runs `go` once.
`stop` in `go` sets `model.running = False`. The sliders and switches are fields of the
generated `Scenario`, along with the world's size, so `FireScenario(density=62, max_pxcor=50)`
changes a run without editing the code. Every random draw goes through the model's seeded
generator (`self.random`), including the order of each `ask`, so a seed fixes the whole run.
The output passes `modelly lint` and ruff.

Exit status: **0** every line was translated (lines that only change the view may have been
dropped), **1** some lines were not translated (the output marks them and stderr lists them),
**2** a usage error (no input, a file that cannot be read, an unknown `--example`).

## What a translation looks like

The NetLogo procedures become methods of the model class. A procedure that a turtle or a patch
runs takes that agent as its argument. Each `ask` block becomes a nested function, run once per
agent by `self.ask(agents, function)`:

```text
to go                                          def go(self):
  if not any? patches with [ pcolor = red ]        if not len([patch for patch in self.patches if patch.pcolor == RED]) > 0:
    [ stop ]                                           self.running = False
  ask patches with [ pcolor = red ] [                  return
    ask neighbors4 with [ pcolor = green ]
      [ ignite ]                                   def ask_1(patch_3):
    set pcolor red - 3.5                               def ask_2(patch_5):
  ]                                                        self.ignite(patch_5)
  tick                                                 self.ask([patch_4 for patch_4 in self.neighbors4(patch_3) if patch_4.pcolor == GREEN], ask_2)
end                                                    patch_3.pcolor = RED - 3.5

                                                   self.ask([patch_2 for patch_2 in self.patches if patch_2.pcolor == RED], ask_1)
                                                   self.tick()
```

## The subset

| NetLogo | Modelly |
|---|---|
| `globals [ ... ]` | model attributes, set to 0 at the start and by `clear-all` |
| sliders and switches (interface tab) | fields of the generated `Scenario`, copied to model attributes |
| the view (`GRAPHICS-WINDOW`) | the `min_pxcor` ... `max_pycor` and `wrap` fields of the `Scenario` |
| patches, `patches-own [ ... ]` | a `Patch` agent per cell of an `OrthogonalMooreGrid` |
| turtles, `turtles-own [ ... ]` | `Turtle` agents (`CellAgent`) |
| `breed [ wolves wolf ]`, `wolves-own [ ... ]` | a subclass of the turtle class per breed |
| `to name [inputs] ... end`, `to-report` | methods of the model |
| `setup`, `go` | run by `__init__` and `step` |
| `clear-all` (`ca`), `reset-ticks`, `tick`, `ticks` | `self.clear_all()`, `self.reset_ticks()`, `self.tick()`, `self.ticks` |
| `ask agents [ ... ]` | `self.ask(agents, function)`: each agent in a new random order, dead turtles skipped |
| `agents with [ ... ]` | a list comprehension |
| `set`, `let` | an assignment to the agent, the model or a local (`nonlocal` when needed) |
| `if`, `ifelse`, `repeat` | `if`, `if`/`else` (or a conditional expression), `for _ in range(n)` |
| `create-turtles`, `create-<breed>`, `hatch`, `hatch-<breed>`, `sprout`, `sprout-<breed>` | `self.create`, `self.hatch`, `self.sprout`, then the block for each new turtle |
| `die`, `stop` | `turtle.die()` then `return`; `return` (and `running = False` in `go`) |
| `fd`/`forward`, `bk`/`back`, `rt`/`right`, `lt`/`left`, `setxy`, `move-to` | methods of the turtle |
| `neighbors`, `neighbors4`, `patch-here`, `turtles-here`, `<breed>-here` | lists of agents |
| `one-of`, `count`, `any?`, `nobody` | `self.one_of`, `len`, `len(...) > 0`, `None` |
| `random`, `random-float`, `random-xcor`, `random-ycor`, `random-pxcor`, `random-pycor` | draws from `self.random` |
| `self`, `myself`, `not`, `and`, `or`, `xor`, `= != < > <= >=`, `+ - * / mod ^`, `abs`, `sqrt` | the Python equivalents |
| `pxcor`, `pycor`, `pcolor`, `xcor`, `ycor`, `heading`, `color`, `who` | attributes of the patch or turtle |
| `red`, `green`, `brown`, ... | the color numbers of `modelly.netlogo.colors` (`red - 3.5` works) |
| `set-default-shape`, `hide-turtle`, `pen-down`, `print`, `show`, ... | dropped (display only), and listed in the report |

The code tab's comments are skipped. A turtle reads and sets the variables of the patch under
it by name, as in NetLogo: `set pcolor brown` in a sheep's code is `turtle.patch.pcolor =
BROWN`. A NetLogo name that would hide a Python keyword or an attribute of the runtime gets a
trailing underscore (a slider called `width` is `width_`); `-` becomes `_` and `?` is dropped
(`grass?` is `grass`).

## Semantics

- **Turtles are patch-centred.** A turtle stands on the cell of a patch. `fd n` moves
  `round(n)` patches along the heading, the heading rounded to the nearest multiple of 45
  degrees (one of the eight neighbours); in a world that does not wrap, the turtle stops at
  the edge. `setxy x y` moves to the patch nearest to the point and raises `ValueError` outside
  a world that does not wrap. `xcor` and `ycor` are the patch's coordinates. Models whose
  behaviour depends on sub-patch positions (flocking, continuous distances) need a human.
- **Agent sets are lists.** `ask` takes a snapshot, shuffles it with the model's generator,
  and skips turtles that died since, as NetLogo does.
- **`die` ends the turtle's code.** The procedure returns; a procedure that may kill its
  turtle is followed, in its caller, by a check that returns when the turtle is dead.
- **A procedure runs as the kind of agent that first calls it** (the observer when nothing
  calls it). Calling it from another kind of agent is reported.
- **Switches** are stored as `0` (on) and `1` (off) in a `.nlogo` file; a slider whose bounds,
  step and value are whole numbers is an `int` field, any other a `float`.
- **The view** is read from the `GRAPHICS-WINDOW` block of the interface tab (the patch
  coordinates and the two wrap flags); without one the world is NetLogo's default, patches
  -16 to 16, wrapping.
- **Data.** A `DataCollector` records `ticks`, every global and the size of every breed (and
  of all turtles) at `reset-ticks` and at every `tick`, where NetLogo updates its plots.

## The report

Each line the translation could not make is printed on stderr, as `file:line: reason: source`,
and kept in the output as a comment at the place it was:

```text
$ python -m modelly.netlogo spiral.nlogo -o spiral.py
spiral.nlogo:2: not translated: unknown command 'layout-circle': layout-circle turtles 5
```

```python
    def setup(self):
        """NetLogo ``to setup``, run by the observer."""
        # NETLOGO line 2, not translated (unknown command 'layout-circle'): layout-circle turtles 5
```

The module's docstring says how many lines are left. Search for `NETLOGO`, write the Python for
each, and run the model's test. A command the translator does not know makes it skip the rest
of that line (and any block the line opens), so one unknown primitive costs one line, not the
procedure.

## The bundled models

Two models ship with the translator, in `modelly/netlogo/models/`, and both translate with no
line left over:

- **`fire.nlogo`**: a fire spreads from the forest's left edge to the trees on the four sides of
  each burning tree. The share of trees burned jumps from a few percent to almost all near a
  density of 59%, the site-percolation threshold of the square lattice. On a 101 x 101 forest,
  averaged over five seeds, the translated model burns 8% of the trees at a density of 50%, 15%
  at 55%, 56% at 59%, 89% at 63% and 97% at 70% (`tests/netlogo/test_translate.py` checks the
  transition with three seeds).
- **`wolf_sheep.nlogo`**: sheep eat grass that regrows after a countdown, wolves eat sheep, and
  both reproduce and starve; the populations oscillate. The test runs it for 100 ticks with
  the default sliders, checks that both populations stay alive and that a seed reproduces the
  run.

Both sources were written for Modelly, inspired by Wilensky's NetLogo models library Wolf Sheep
Predation (1997) and Fire (1997); sources written from the published model descriptions, not
copied. (Wilensky, U. 1997. NetLogo Wolf Sheep Predation model and NetLogo Fire model. Center for
Connected Learning and Computer-Based Modeling, Northwestern University, Evanston, IL.) The
models library code is under a non-commercial licence and is not included.

## Limits

- Not supported: links, `of`, `list` and other list primitives, `while`, `foreach`, `map`,
  anonymous procedures, `distance`, `in-radius`, `face`, `patch-at`, `set breed`, `stop` inside a
  reporter, extensions, string primitives, choosers and input boxes (reported as interface
  widgets). Each one is reported where it appears.
- Positions are whole patches (see Semantics): models that rely on fractional turtle positions
  translate and run, but do not behave like the original.
- `patches` is a list of every patch, so `ask patches with [...]` visits every patch once per
  call, as in NetLogo. A large world is slower than NetLogo's compiled engine; for speed, move a
  translated phase to the model as columns (see [Vectorised phases](vectorised_phases.md)).
- The translator checks the names it reads against the declarations, but it does not type-check:
  a NetLogo program that NetLogo itself rejects may still translate.
