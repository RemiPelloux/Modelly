"""The catalogue of zoo models: one ``ZooModel`` per reference model.

Each model lives in ``modelly/zoo/<name>/model.py``, a single module that imports only
public ``modelly`` modules, so ``copy_model`` can write it into a new project unchanged.
The module docstring describes the model, its validation and its references.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path


@dataclass(frozen=True)
class ZooModel:
    """One reference model of the zoo.

    Attributes:
        name: the zoo name (``modelly zoo info <name>``), also its package name.
        title: a human-readable title.
        field: the scientific field.
        model: the ``Model`` subclass, by name, in ``modelly.zoo.<name>.model``.
        scenario: its ``Scenario`` subclass, by name.
        summary: one sentence.
        validation: what the validation test checks.
    """

    name: str
    title: str
    field: str
    model: str
    scenario: str
    summary: str
    validation: str

    @property
    def module(self) -> str:
        """The dotted name of the model's module."""
        return f"modelly.zoo.{self.name}.model"

    @property
    def source(self) -> Path:
        """The path of the model's source file."""
        return Path(importlib.util.find_spec(self.module).origin)

    def load(self) -> tuple[type, type]:
        """Import the module and return ``(model class, scenario class)``."""
        module = importlib.import_module(self.module)
        return getattr(module, self.model), getattr(module, self.scenario)

    def doc(self) -> str:
        """The model module's docstring: the description and the references."""
        return importlib.import_module(self.module).__doc__ or ""


MODELS: tuple[ZooModel, ...] = (
    ZooModel(
        "age_seir",
        "Age-structured SEIR with contact matrices",
        "epidemiology",
        "AgeSEIR",
        "SEIRScenario",
        "SEIR over age groups mixing through a contact matrix, as binomial cohorts.",
        "attack rate against the final-size relation, within the CLT bound",
    ),
    ZooModel(
        "vector_borne",
        "Vector-borne transmission on a landscape",
        "epidemiology",
        "VectorBorne",
        "VectorScenario",
        "Ross-Macdonald transmission between moving hosts and mosquito cohorts per cell.",
        "outbreak size ordered like the Ross-Macdonald R0 as vector density grows",
    ),
    ZooModel(
        "hospital_epidemic",
        "Epidemic coupled to hospital capacity",
        "epidemiology",
        "HospitalEpidemic",
        "HospitalScenario",
        "SIR agents whose admissions drive a hospital stock-flow ODE that damps contacts.",
        "final size; hospital against its exact linear solution; admissions mass balance",
    ),
    ZooModel(
        "energy_budget",
        "Individual-based population with energy budgets",
        "ecology",
        "EnergyBudget",
        "EnergyScenario",
        "Foragers that eat, pay a metabolic cost, reproduce and starve on a resource grid.",
        "mean density against the carrying capacity from the energy balance",
    ),
    ZooModel(
        "nutrient_foragers",
        "Foragers on a diffusing nutrient field",
        "ecology",
        "NutrientForagers",
        "NutrientScenario",
        "Foragers eat from a nutrient that enters at a river bank and diffuses inland.",
        "carrying capacity from the energy balance; nutrient budget closed to round-off",
    ),
    ZooModel(
        "forest_fire",
        "Forest fire and succession on a raster",
        "ecology",
        "ForestFire",
        "ForestScenario",
        "Fire spreading through a tree raster, with optional regrowth and lightning.",
        "burnt share jumps at the site-percolation threshold",
    ),
    ZooModel(
        "order_book",
        "Continuous double auction (zero-intelligence order book)",
        "economics",
        "OrderBook",
        "OrderBookScenario",
        "Random limit, market and cancel orders (per resting order) in a limit order book.",
        "fat tails: excess kurtosis far above the normal-returns standard error",
    ),
    ZooModel(
        "kinetic_wealth",
        "Boltzmann wealth exchange",
        "economics",
        "KineticWealth",
        "KineticScenario",
        "Random pairs pass one unit of money: the Boltzmann-Gibbs distribution emerges.",
        "stationary distribution and Gini against the exact uniform-configuration law",
    ),
    ZooModel(
        "bouchaud_mezard",
        "Bouchaud-Mezard wealth condensation",
        "economics",
        "BouchaudMezard",
        "BouchaudMezardScenario",
        "Multiplicative returns plus exchange: an inverse-gamma wealth distribution.",
        "Gini against the inverse-gamma law, rising with the noise-to-exchange ratio",
    ),
    ZooModel(
        "deffuant",
        "Deffuant bounded-confidence opinion dynamics",
        "sociology",
        "Deffuant",
        "DeffuantScenario",
        "Random pairs of agents compromise when their opinions are close enough.",
        "consensus for a wide confidence bound, about 1/(2 eps) clusters for a narrow one",
    ),
    ZooModel(
        "hegselmann_krause",
        "Hegselmann-Krause bounded-confidence opinion dynamics",
        "sociology",
        "HegselmannKrause",
        "HKScenario",
        "Every agent moves to the mean opinion of those within its confidence bound.",
        "cluster count falls to consensus as the confidence bound grows",
    ),
    ZooModel(
        "axelrod",
        "Axelrod culture dissemination",
        "political science",
        "Axelrod",
        "AxelrodScenario",
        "Neighbours on a grid copy cultural traits with a probability set by similarity.",
        "monoculture for few traits, many cultural regions for many traits",
    ),
    ZooModel(
        "nagel_schreckenberg",
        "Nagel-Schreckenberg traffic",
        "transport",
        "NagelSchreckenberg",
        "TrafficScenario",
        "Cars on a ring road accelerate, brake to the gap ahead and dawdle at random.",
        "fundamental diagram: exact min(rho v, 1 - rho) without dawdling, rise then fall",
    ),
    ZooModel(
        "bass_diffusion",
        "Bass diffusion of innovation on a network",
        "energy",
        "BassDiffusion",
        "BassScenario",
        "Households adopt from advertising and from adopting neighbours.",
        "adoption curve within Euler error + 5 sd of the Bass ODE; slower when sparse",
    ),
)


def names() -> list[str]:
    """The zoo names, in catalogue order."""
    return [entry.name for entry in MODELS]


def get(name: str) -> ZooModel:
    """The zoo model called ``name``.

    Raises:
        KeyError: if there is none; the message suggests the closest names.
    """
    for entry in MODELS:
        if entry.name == name:
            return entry
    close = get_close_matches(name, names())
    hint = f" Did you mean {', '.join(close)}?" if close else ""
    raise KeyError(f"No zoo model named {name!r}.{hint} See `modelly zoo list`.")
