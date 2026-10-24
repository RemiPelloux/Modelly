"""Test functions with known indices, and a small importable model."""

import math

import numpy as np

from modelly import Model
from modelly.scenarios import Scenario

ISHIGAMI_A, ISHIGAMI_B = 7.0, 0.1
G_COEFFICIENTS = (0.0, 1.0, 4.5, 9.0, 99.0, 99.0)


def ishigami(x1, x2, x3):
    """The Ishigami function on [-pi, pi]^3."""
    return (
        math.sin(x1)
        + ISHIGAMI_A * math.sin(x2) ** 2
        + ISHIGAMI_B * x3**4 * math.sin(x1)
    )


def ishigami_indices():
    """The analytical first-order and total indices of the Ishigami function."""
    a, b, pi = ISHIGAMI_A, ISHIGAMI_B, math.pi
    v1 = 0.5 * (1 + b * pi**4 / 5) ** 2
    v2 = a**2 / 8
    v13 = b**2 * pi**8 * (1 / 18 - 1 / 50)
    total = v1 + v2 + v13
    first = np.array([v1, v2, 0.0]) / total
    return first, np.array([v1 + v13, v2, v13]) / total


def g_function(**x):
    """The Sobol G function with the coefficients ``G_COEFFICIENTS``."""
    value = 1.0
    for index, a in enumerate(G_COEFFICIENTS):
        value *= (abs(4 * x[f"x{index}"] - 2) + a) / (1 + a)
    return value


def g_indices():
    """The analytical first-order and total indices of the G function."""
    partial = np.array([1 / (3 * (1 + a) ** 2) for a in G_COEFFICIENTS])
    total = np.prod(1 + partial) - 1
    rest = np.array([np.prod(np.delete(1 + partial, i)) for i in range(len(partial))])
    return partial / total, partial * rest / total


def linear(a, b, c, d):
    """A linear function of four inputs (for a spec naming a function)."""
    return 3 * a + 2 * b + c + 0 * d


class ResponseScenario(Scenario):
    """Four inputs of very different weight."""

    a: float = 0.5
    b: float = 0.5
    c: float = 0.5
    d: float = 0.5


class Response(Model):
    """``value = 10 a + 4 b^2 + c + noise``; ``d`` does nothing."""

    def __init__(self, scenario: ResponseScenario = ResponseScenario):  # noqa: D107
        super().__init__(scenario=scenario)
        self.value = 0.0

    def step(self):  # noqa: D102
        s = self.scenario
        self.value = 10 * s.a + 4 * s.b**2 + s.c + 0.05 * float(self.rng.normal())
