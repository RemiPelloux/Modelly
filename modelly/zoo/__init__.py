"""The model zoo: validated reference models from many fields.

Each model is a package ``modelly.zoo.<name>`` whose ``model`` module holds a ``Scenario``
and a ``Model``, with its references in the docstring and a validation test against an
analytical or well-known result in ``tests/zoo``. ``modelly zoo list`` shows them and
``modelly zoo copy <name> <dir>`` starts a project from one::

    from modelly.zoo import get

    AgeSEIR, SEIRScenario = get("age_seir").load()
    model = AgeSEIR(SEIRScenario(rng=1))
    model.run()
"""

from modelly.zoo.copy import copy_model
from modelly.zoo.registry import MODELS, ZooModel, get, names

__all__ = ["MODELS", "ZooModel", "copy_model", "get", "names"]
