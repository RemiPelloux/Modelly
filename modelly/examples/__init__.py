"""The example models, importable by name: ``from modelly.examples import Schelling``.

Each model is imported on first use, so importing one example (or ``modelly.examples``)
does not import the others and their dependencies (networkx for the network examples): a
browser export of one example loads only the packages that example needs.
"""

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modelly.examples.advanced.alliance_formation.model import (
        MultiLevelAllianceModel,
    )
    from modelly.examples.advanced.epstein_civil_violence.model import (
        EpsteinCivilViolence,
    )
    from modelly.examples.advanced.pd_grid.model import PdGrid
    from modelly.examples.advanced.sugarscape_g1mt.model import SugarscapeG1mt
    from modelly.examples.advanced.wolf_sheep.model import WolfSheep
    from modelly.examples.basic.boid_flockers.model import BoidFlockers
    from modelly.examples.basic.boltzmann_wealth_model.model import BoltzmannWealth
    from modelly.examples.basic.conways_game_of_life.model import ConwaysGameOfLife
    from modelly.examples.basic.schelling.model import Schelling
    from modelly.examples.basic.virus_on_network.model import VirusOnNetwork
    from modelly.examples.behaviour.tram_model.model import TransitSystem

_MODULES = {
    "MultiLevelAllianceModel": "modelly.examples.advanced.alliance_formation.model",
    "EpsteinCivilViolence": "modelly.examples.advanced.epstein_civil_violence.model",
    "PdGrid": "modelly.examples.advanced.pd_grid.model",
    "SugarscapeG1mt": "modelly.examples.advanced.sugarscape_g1mt.model",
    "WolfSheep": "modelly.examples.advanced.wolf_sheep.model",
    "BoidFlockers": "modelly.examples.basic.boid_flockers.model",
    "BoltzmannWealth": "modelly.examples.basic.boltzmann_wealth_model.model",
    "ConwaysGameOfLife": "modelly.examples.basic.conways_game_of_life.model",
    "Schelling": "modelly.examples.basic.schelling.model",
    "VirusOnNetwork": "modelly.examples.basic.virus_on_network.model",
    "TransitSystem": "modelly.examples.behaviour.tram_model.model",
}

__all__ = [
    "BoidFlockers",
    "BoltzmannWealth",
    "ConwaysGameOfLife",
    "EpsteinCivilViolence",
    "MultiLevelAllianceModel",
    "PdGrid",
    "Schelling",
    "SugarscapeG1mt",
    "TransitSystem",
    "VirusOnNetwork",
    "WolfSheep",
]


def __getattr__(name):
    """Import the example model ``name`` from its module on first access."""
    if name not in _MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(_MODULES[name]), name)
    globals()[name] = value
    return value


def __dir__():
    """The module's names, the example models included."""
    return sorted({*globals(), *_MODULES})
