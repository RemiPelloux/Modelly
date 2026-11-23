# Figures and animations

From exploring a run to a figure in a paper: `modelly.viz.styles` sets Matplotlib up for a
journal, `modelly.viz.palettes` holds colour-blind-safe colours, and `modelly.viz.animation`
turns any space view into a GIF or an MP4. Everything here draws on plain Matplotlib figures,
without a window or a notebook, so it runs headless on Windows, macOS and Linux, in a script
or on a server.

## Publication styles

```python
import matplotlib.pyplot as plt

from modelly.examples import BoltzmannWealth
from modelly.viz import styles

model = BoltzmannWealth()
model.run_for(100)
gini = model.datacollector.get_model_vars_dataframe()["Gini"]

with styles.paper("nature", columns=1):
    fig, ax = plt.subplots()
    ax.plot(gini)
    ax.set_xlabel("step")
    ax.set_ylabel("Gini coefficient")
    fig.savefig("gini.pdf")
```

Inside the `with` block, figures are one or two journal columns wide (height from the golden
ratio), fonts are 7 to 8 points and embedded as TrueType (`pdf.fonttype` 42, which journals
require), the top and right spines are off, the colour cycle is colour-blind safe, and figures
save at 300 dpi with a tight bounding box. The previous settings come back when the block ends.

| Journal | Single column | Double column |
|---|---|---|
| `nature` | 89 mm (3.50 in) | 183 mm (7.20 in) |
| `science` | 57 mm (2.24 in) | 121 mm (4.76 in) |
| `pnas` | 87 mm (3.43 in) | 178 mm (7.01 in) |
| `elsevier` | 90 mm (3.54 in) | 190 mm (7.48 in) |
| `plos` | 5.2 in | 7.5 in |
| `ieee` | 3.5 in | 7.16 in |

The widths are those the journals' author guides state; check the current guide before
submitting.

```python
styles.figure_size("ieee", columns=2)  # (7.16, 4.43): width, height in inches
styles.figure_size("ieee", columns=2, aspect=1)  # square
params = styles.rc_params(
    "pnas", columns=1, palette="tol_bright"
)  # the settings as a dict

with styles.paper("science"), plt.rc_context({"font.size": 6}):
    ...  # adjust one setting on top of a style
```

## Colour-blind-safe palettes

| Name | Colours | Source |
|---|---|---|
| `okabe_ito` (default) | 8 | Okabe and Ito |
| `tol_bright` | 7 | Paul Tol |
| `tol_vibrant` | 7 | Paul Tol |
| `tol_muted` | 9 | Paul Tol |

```python
from modelly.viz.palettes import OKABE_ITO, PALETTES

with styles.paper(palette="tol_muted"):
    ...

ax.plot(x, y, color=OKABE_ITO[4])  # one colour by hand
```

The palettes are plain tuples of hex strings, so they work with Altair as well.

## One portrayal for every backend

An agent portrayal is a function that returns an `AgentPortrayalStyle` (`color`, `size`,
`marker`, `alpha`, `zorder`, `edgecolors`, `linewidths`, `tooltip`, `filled`). The same
function drives the Matplotlib and Altair backends of `SpaceRenderer`, the space views of
`SolaraViz`, Modelly Studio, the figures below and the animations: the style classes, their
defaults and the conversion of the older portrayal dicts live in one module,
`modelly.viz.render.portrayal`.

When you have no portrayal yet, `ClassColours()` gives each agent class its own colour from a
palette:

```python
from modelly.viz.render.portrayal import ClassColours

portrayal = ClassColours()  # Okabe-Ito
portrayal = ClassColours(palette=PALETTES["tol_bright"], size=20)
```

## A figure of the space

```python
from modelly.viz.mpl.figure import space_figure

with styles.paper("nature", columns=1):
    fig = space_figure(
        model, agent_portrayal=None, figsize=styles.figure_size("nature")
    )
    fig.savefig("space.pdf")
```

`space_figure` draws the model's space (`model.grid`, else `model.space`) and agents with
`SpaceRenderer` on a new figure: grids, hexagonal grids, networks, continuous spaces and
Voronoi grids.

## Animations

```python
from modelly.examples import WolfSheep
from modelly.viz.animation import AnimationOptions, frames_from_run, save_animation

model = WolfSheep()
save_animation(frames_from_run(model, steps=200), "wolf_sheep.gif")
save_animation(
    frames_from_run(WolfSheep(), steps=200, every=2),
    "wolf_sheep.mp4",
    AnimationOptions(fps=24, figsize=(6, 6), dpi=120),
)
```

The frames are models: `frames_from_run(model, steps, every=1)` steps the model and yields it
at the start and after every `every` steps; `frames_from_timeline(recorder)` yields the model
at each checkpoint of a [time travel](timetravel.md) recording, so a run recorded once can be
animated afterwards:

```python
from modelly.timetravel import Recorder
from modelly.viz.animation import frames_from_timeline

with Recorder(model, every=5) as recorder:
    model.run_for(500)
save_animation(frames_from_timeline(recorder), "run.gif")
```

`save_animation(models, path, options=None, agent_portrayal=None)` draws each frame with
`space_figure` and returns the number of frames written. The suffix picks the format:

| Format | Needs | Notes |
|---|---|---|
| `.gif` | Pillow, installed with Matplotlib | loops by default (`AnimationOptions(loop=False)` plays once); identical consecutive frames are merged |
| `.mp4` | the `video` extra: `pip install "modelly-abm[video]"` | H.264 through `imageio-ffmpeg`, which ships an ffmpeg binary for Windows, macOS and Linux: nothing to install system-wide |

Frames are padded with white to a multiple of 16 pixels, which video codecs need. `fps`,
`figsize` and `dpi` set the frame rate and the frame size (`figsize` times `dpi` pixels).

The API is in [Viz](apis/viz.md).
