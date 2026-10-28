"""The Pyodide packages a model needs: the ones its import and its first steps load.

``python -m modelly.web.packages TARGET STEPS SEED`` builds the model in a fresh
interpreter, runs it, and prints the distributions of the third-party modules imported
after ``import modelly`` as JSON. ``needed_packages`` runs it in a subprocess, so what the
exporting process imported before does not count. ``import modelly`` itself needs only
``CORE`` in the browser; the page loads nothing else, so an optional dependency the model
does not use (matplotlib for networkx, pyarrow for pandas) is not downloaded.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib.metadata import packages_distributions

from modelly.profile.loader import TargetError

# What ``import modelly`` loads in Pyodide (pandas 3 no longer needs pytz).
CORE = ("numpy", "pandas", "python-dateutil", "six")
OWN = frozenset({"modelly-abm"})


class ModelRunError(TargetError):
    """The model was found but raised while it was built or run."""


def normalise(name: str) -> str:
    """A distribution name as Pyodide's lock file spells it (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _top_level_modules() -> set[str]:
    """The top-level names of the imported modules."""
    return {name.partition(".")[0] for name in sys.modules}


def distributions_of(modules: set[str]) -> set[str]:
    """The installed distributions that provide ``modules``, stdlib and Modelly excluded."""
    providers = packages_distributions()
    found = set()
    for module in modules - set(sys.stdlib_module_names):
        found.update(normalise(dist) for dist in providers.get(module, ()))
    return found - OWN


def probe(target: str, steps: int, seed: int) -> list[str]:
    """Build and run ``target`` here; the distributions it imported, CORE included."""
    import modelly  # noqa: F401, PLC0415 - the baseline is what this import loads
    from modelly.profile.loader import build_model  # noqa: PLC0415
    from modelly.studio.loader import load_model_class  # noqa: PLC0415

    before = _top_level_modules()
    model_class = load_model_class(target)
    model = build_model(model_class, {}, seed)
    for _ in range(steps):
        if not model.running:
            break
        model.step()
    # The model's own package ships in the site, not as a Pyodide package.
    before.add(model_class.__module__.partition(".")[0])
    extra = distributions_of(_top_level_modules() - before)
    return sorted(set(CORE) | extra)


def needed_packages(target: str, steps: int, seed: int) -> list[str]:
    """``probe`` in a fresh interpreter.

    Raises:
        ModelRunError: When the model cannot be imported, built or run.
    """
    command = [sys.executable, "-m", __name__, target, str(steps), str(seed)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ModelRunError(f"{target} did not run {steps} steps:\n{result.stderr}")
    return json.loads(result.stdout.strip().splitlines()[-1])


__all__ = ["CORE", "ModelRunError", "distributions_of", "needed_packages", "normalise"]

if __name__ == "__main__":
    name, count, seed_text = sys.argv[1:]
    sys.stdout.write(json.dumps(probe(name, int(count), int(seed_text))) + "\n")
