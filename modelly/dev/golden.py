"""Golden run digests of every bundled example: ``python -m modelly.dev golden``.

Each example in ``EXAMPLES`` runs ``steps`` steps from seed ``SEED``; the digest of its
collected data and final state (``modelly.dev.digest``) is compared with the one in
``tests/determinism/golden.json``. Every platform, compiled or pure Python, must
reproduce the same digests. ``--update`` rewrites the file after a deliberate change.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from modelly.dev.digest import ENCODING, run_digest

if TYPE_CHECKING:
    from modelly.core.model import Model

SEED = 42
DEFAULT_STEPS = 10
FORMAT = 1
GOLDEN = Path("tests") / "determinism" / "golden.json"
JSON_INDENT = 2
# Significant digits kept for outputs computed through libm or BLAS (exp, log, pow,
# arctan2, norm): those may differ in the last bit between platforms.
LIBM_DIGITS = 10
DYNAMIC_CLASSES = "meta-agent classes are created at run time and cannot be pickled"
RATE_CLOSURES = "ContinuousState rates and Threshold callbacks are closures"
GEO_LIBRARIES = (
    "projections and geometry come from the PROJ and GEOS builds inside the pyproj and\n"
    "shapely wheels, which differ between platforms"
).replace("\n", " ")
# Where a golden file was written; machine_only examples are compared there only.
PLATFORM = f"{sys.platform}-{platform.machine().lower()}"
_PACKAGE = "modelly.examples."


@dataclass(frozen=True)
class Example:
    """A bundled example as the determinism suite runs it.

    Attributes:
        name: key in the golden file.
        model: ``module:Class`` of the model, relative to ``modelly.examples``.
        scenario: ``module:Class`` of its scenario, or None when the model takes ``rng``.
        steps: how many steps to run.
        float_digits: significant digits of floats in the golden digest, or None (exact).
        requires: optional modules the example needs; it is skipped without them.
        no_checkpoint: why the example cannot be checkpointed yet, or None.
        machine_only: why the golden digest holds on the recording platform only, or None.
    """

    name: str
    model: str
    scenario: str | None = None
    steps: int = DEFAULT_STEPS
    float_digits: int | None = None
    requires: tuple[str, ...] = ()
    no_checkpoint: str | None = None
    machine_only: str | None = None

    def available(self) -> bool:
        """Whether every optional module the example needs is installed."""
        return all(importlib.util.find_spec(name) for name in self.requires)

    def build(self, seed: int = SEED) -> Model[Any, Any]:
        """A new model of this example, seeded with ``seed``."""
        model_class = _resolve(self.model)
        if self.scenario is None:
            model: Model[Any, Any] = model_class(rng=seed)
        else:
            model = model_class(scenario=_resolve(self.scenario)(rng=seed))
        return model

    def run(self, seed: int = SEED) -> Model[Any, Any]:
        """A model of this example after ``steps`` steps."""
        model = self.build(seed)
        model.run_for(self.steps)
        return model


def _resolve(target: str) -> Any:
    module, name = target.split(":")
    return getattr(importlib.import_module(_PACKAGE + module), name)


EXAMPLES = (
    Example(
        "alliance_formation",
        "advanced.alliance_formation.model:MultiLevelAllianceModel",
        "advanced.alliance_formation.model:AllianceScenario",
        float_digits=LIBM_DIGITS,
        requires=("networkx",),
        no_checkpoint=DYNAMIC_CLASSES,
    ),
    Example(
        "epstein_civil_violence",
        "advanced.epstein_civil_violence.model:EpsteinCivilViolence",
        "advanced.epstein_civil_violence.model:EpsteinScenario",
        float_digits=LIBM_DIGITS,
    ),
    Example(
        "pd_grid",
        "advanced.pd_grid.model:PdGrid",
        "advanced.pd_grid.model:PrisonersDilemmaScenario",
    ),
    Example(
        "sugarscape_g1mt",
        "advanced.sugarscape_g1mt.model:SugarscapeG1mt",
        "advanced.sugarscape_g1mt.model:SugarScapeScenario",
        float_digits=LIBM_DIGITS,
    ),
    Example(
        "wolf_sheep",
        "advanced.wolf_sheep.model:WolfSheep",
        "advanced.wolf_sheep.model:WolfSheepScenario",
    ),
    Example(
        "boid_flockers",
        "basic.boid_flockers.model:BoidFlockers",
        "basic.boid_flockers.model:BoidsScenario",
        float_digits=LIBM_DIGITS,
    ),
    Example(
        "boltzmann_wealth_model",
        "basic.boltzmann_wealth_model.model:BoltzmannWealth",
        "basic.boltzmann_wealth_model.model:BoltzmannScenario",
    ),
    Example(
        "conways_game_of_life", "basic.conways_game_of_life.model:ConwaysGameOfLife"
    ),
    Example(
        "schelling",
        "basic.schelling.model:Schelling",
        "basic.schelling.model:SchellingScenario",
    ),
    Example(
        "virus_on_network",
        "basic.virus_on_network.model:VirusOnNetwork",
        requires=("networkx",),
    ),
    Example(
        "tram_model",
        "behaviour.tram_model.model:TransitSystem",
        "behaviour.tram_model.model:TramScenario",
        no_checkpoint=RATE_CLOSURES,
    ),
    Example("llm_opinions", "llm.llm_opinions.model:LLMOpinions"),
    Example(
        "commuting_city",
        "spatial.commuting_city.model:CommutingCity",
        "spatial.commuting_city.model:CommutingScenario",
        float_digits=LIBM_DIGITS,
        requires=("geopandas",),
        machine_only=GEO_LIBRARIES,
    ),
    Example(
        "layered_epidemic",
        "spatial.layered_epidemic.model:LayeredEpidemic",
        "spatial.layered_epidemic.model:EpidemicScenario",
        float_digits=LIBM_DIGITS,
    ),
)
EXAMPLES_BY_NAME = {example.name: example for example in EXAMPLES}


def golden_digest(example: Example, seed: int = SEED, *, exact: bool = False) -> str:
    """The digest of ``example`` as the golden file records it, or unrounded if ``exact``."""
    return run_digest(example.run(seed), None if exact else example.float_digits)


def current_digests(*, exact: bool = False) -> dict[str, str]:
    """Golden digests of every available example, computed now (unrounded if ``exact``)."""
    return {e.name: golden_digest(e, exact=exact) for e in EXAMPLES if e.available()}


def golden_record(
    digests: dict[str, str], recorded_on: str = PLATFORM
) -> dict[str, Any]:
    """The golden file contents for ``digests``, written on ``recorded_on``."""
    examples = {
        name: {
            "steps": EXAMPLES_BY_NAME[name].steps,
            "float_digits": EXAMPLES_BY_NAME[name].float_digits,
            "sha256": digests[name],
        }
        for name in sorted(digests)
    }
    return {
        "format": FORMAT,
        "seed": SEED,
        "recorded_on": recorded_on,
        "examples": examples,
    }


def read_golden(path: Path) -> dict[str, str]:
    """The recorded digests in the golden file at ``path``, by example name."""
    record = json.loads(path.read_text(encoding=ENCODING))
    return {name: entry["sha256"] for name, entry in record["examples"].items()}


def recorded_platform(path: Path) -> str:
    """The platform the golden file at ``path`` was written on."""
    platform_name: str = json.loads(path.read_text(encoding=ENCODING))["recorded_on"]
    return platform_name


def write_golden(path: Path, digests: dict[str, str]) -> None:
    """Write the golden file for ``digests`` to ``path`` (LF line endings)."""
    text = json.dumps(golden_record(digests), indent=JSON_INDENT, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(ENCODING))


def differences(recorded: dict[str, str], current: dict[str, str]) -> list[str]:
    """One line per example whose current digest is missing or differs from the record."""
    lines = []
    for name in sorted(current):
        if name not in recorded:
            lines.append(f"{name}: no golden digest (run golden --update)")
        elif recorded[name] != current[name]:
            lines.append(f"{name}: {current[name]} != golden {recorded[name]}")
    return lines
