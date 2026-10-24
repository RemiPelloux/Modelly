"""Copy a zoo model into a folder of its own, to start a project from it."""

from __future__ import annotations

from pathlib import Path

from modelly.zoo.registry import ZooModel, get

MODEL_FILE = "model.py"
README_FILE = "README.md"

README_TEMPLATE = """\
# {title}

{summary}

Copied from the Modelly zoo (`modelly zoo info {name}`). Field: {field}.
Validated in the zoo against: {validation}.

```python
from model import {model}, {scenario}

model = {model}({scenario}(rng=42))
model.run()
model.datacollector.get_model_vars_dataframe()
```

The model's description and references are in the docstring of `model.py`.
"""


def parameters(entry: ZooModel) -> dict[str, object]:
    """The scenario's parameters and their default values."""
    _, scenario = entry.load()
    return dict(scenario._scenario_defaults)


def readme(entry: ZooModel) -> str:
    """The README written next to a copied model."""
    return README_TEMPLATE.format(**vars(entry))


def copy_model(name: str, directory: str | Path) -> list[Path]:
    """Write zoo model ``name`` into ``directory`` as ``model.py`` and ``README.md``.

    The folder is created if needed. Nothing is overwritten.

    Example:
        >>> import tempfile
        >>> folder = Path(tempfile.mkdtemp()) / "my_epidemic"
        >>> [path.name for path in copy_model("age_seir", folder)]
        ['model.py', 'README.md']

    Raises:
        KeyError: if there is no zoo model ``name``.
        FileExistsError: if ``model.py`` or ``README.md`` already exists there.
    """
    entry = get(name)
    folder = Path(directory)
    targets = {
        folder / MODEL_FILE: entry.source.read_text(encoding="utf-8"),
        folder / README_FILE: readme(entry),
    }
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError(f"Not overwriting {', '.join(existing)}.")
    folder.mkdir(parents=True, exist_ok=True)
    for path, text in targets.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return list(targets)
