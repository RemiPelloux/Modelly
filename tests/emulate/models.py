"""Benchmark functions and the zoo-model outputs the emulation tests use."""

import math

import numpy as np

from modelly.zoo.age_seir.model import State

PI = math.pi
BRANIN_B = 5.1 / (4 * PI**2)
BRANIN_C = 5 / PI
BRANIN_T = 1 / (8 * PI)
BRANIN_R = 6.0
BRANIN_S = 10.0


def branin(x1, x2):
    """The Branin function on [-5, 10] x [0, 15] (Dixon and Szego 1978)."""
    bowl = (x2 - BRANIN_B * x1**2 + BRANIN_C * x1 - BRANIN_R) ** 2
    return bowl + BRANIN_S * (1 - BRANIN_T) * math.cos(x1) + BRANIN_S


def infectious(model):
    """The share of the population infectious."""
    return float(model.counts()[:, State.I].sum() / model.sizes.sum())


def recovered(model):
    """The share of the population recovered."""
    return float(model.counts()[:, State.R].sum() / model.sizes.sum())


def peak_step(series):
    """The step at which a series peaks (the epidemic's timing)."""
    return float(np.argmax(series))
