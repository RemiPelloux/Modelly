"""The 2.0 typed scenarios, announced in 1.5: what a Scenario subclass warns about."""

import warnings

import numpy as np
import pytest

from modelly._deprecation import ModellyDeprecationWarning
from modelly.scenarios import Scenario


class Typed(Scenario):
    """Every field annotated."""

    beta: float = 0.3
    steps: int = 100
    name: str = "run"


def no_warning(make):
    """Call ``make`` and fail on any Modelly deprecation."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", ModellyDeprecationWarning)
        return make()


def test_an_attribute_without_an_annotation_warns_with_its_fix():
    """2.0 will not see ``gamma = 0.1`` as a field: the warning shows the annotated form."""
    with pytest.warns(ModellyDeprecationWarning, match=r"gamma: float = 0.1"):

        class Loose(Scenario):
            beta: float = 0.3
            gamma = 0.1

            def helper(self):
                return self.beta

            @property
            def total(self):
                return self.beta

    assert Loose(rng=1).gamma == 0.1  # it still works in 1.5


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [({"betta": 0.2}, r"betta=.*does not declare"), ({"steps": "100"}, r"annotated int"),
     ({"beta": "fast"}, r"annotated float"), ({"name": 3}, r"annotated str")],
)  # fmt: skip
def test_undeclared_or_mistyped_parameters_warn(kwargs, match):
    """Each still builds, as in 1.4, and names what to change."""
    with pytest.warns(ModellyDeprecationWarning, match=match):
        scenario = Typed(rng=1, **kwargs)
    assert all(getattr(scenario, k) == v for k, v in kwargs.items())


def test_values_of_the_annotated_type_do_not_warn():
    """An int for a float, numpy numbers, the plain Scenario and an untyped subclass are fine."""
    no_warning(lambda: Typed(rng=1, beta=1, steps=np.int64(5), name="x"))
    no_warning(lambda: Typed(rng=1, beta=np.float64(0.2)))
    no_warning(lambda: Scenario(rng=1, density=0.8, anything="goes"))

    class Untyped(Scenario):
        pass

    no_warning(lambda: Untyped(rng=1, density=0.8))


def test_the_zoo_scenarios_are_already_typed():
    """No zoo scenario warns, so 2.0 takes them as they are."""
    from modelly.zoo.registry import MODELS  # noqa: PLC0415

    for entry in MODELS:
        _, scenario = entry.load()
        no_warning(lambda scenario=scenario: scenario(rng=1))
