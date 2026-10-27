"""A small neural emulator: an ensemble of multilayer perceptrons, numpy only.

Each member is a fully connected network (``tanh`` hidden layers, a linear
output per emulated output) trained on the standardised data by full-batch Adam
on the mean squared error plus a weight penalty. The members differ only in
their random initial weights; the ensemble's mean is the prediction and the
spread between members its standard deviation (a "deep ensemble",
Lakshminarayanan, Pritzel and Blundell 2017). It needs no deep-learning library
and suits a few hundred to a few thousand runs, where a Gaussian process gets
slow; with few runs the Gaussian process is usually more accurate.

Every weight is drawn from ``settings.seed``: the same data and seed give the
same emulator.

Example:
    >>> import numpy as np
    >>> units = np.linspace(0, 1, 40)[:, None]
    >>> emulator = NeuralEmulator.fit(units, units[:, 0] ** 2)
    >>> bool(abs(emulator.predict([[0.5]])[0][0, 0] - 0.25) < 0.05)
    True
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np

from modelly.emulate.base import Emulator, as_columns, output_names
from modelly.experiments.space import ScenarioSpace

Layer = tuple[np.ndarray, np.ndarray]  # weights [inputs, outputs], biases [outputs]
ADAM_DECAY = (0.9, 0.999)  # Adam's first- and second-moment decay rates
ADAM_EPSILON = 1e-8
DEFAULT_HIDDEN = (32, 32)
DEFAULT_MEMBERS = 5
DEFAULT_EPOCHS = 2000
DEFAULT_LEARNING_RATE = 0.01
DEFAULT_PENALTY = 1e-5


@dataclass(frozen=True)
class NeuralSettings:
    """How the ensemble is built and trained.

    Args:
        hidden: the width of each hidden layer.
        members: the number of networks in the ensemble.
        epochs: full-batch Adam steps per network.
        learning_rate: Adam's step size.
        penalty: the weight of the squared-weights penalty.
        seed: the root of every initial weight.
    """

    hidden: tuple[int, ...] = DEFAULT_HIDDEN
    members: int = DEFAULT_MEMBERS
    epochs: int = DEFAULT_EPOCHS
    learning_rate: float = DEFAULT_LEARNING_RATE
    penalty: float = DEFAULT_PENALTY
    seed: int = 0


def _initial(sizes: Sequence[int], rng: np.random.Generator) -> list[Layer]:
    """Glorot-normal weights and zero biases for layers of ``sizes``."""
    return [
        (rng.normal(0.0, np.sqrt(2.0 / (n_in + n_out)), (n_in, n_out)), np.zeros(n_out))
        for n_in, n_out in pairwise(sizes)
    ]


def _forward(layers: list[Layer], x: np.ndarray) -> list[np.ndarray]:
    """The input, every hidden activation and the output of one network."""
    activations = [x]
    for weights, biases in layers[:-1]:
        activations.append(np.tanh(activations[-1] @ weights + biases))
    weights, biases = layers[-1]
    return [*activations, activations[-1] @ weights + biases]


def _gradients(
    layers: list[Layer], x: np.ndarray, y: np.ndarray, penalty: float
) -> list[Layer]:
    """The gradient of the penalised mean squared error, layer by layer."""
    activations = _forward(layers, x)
    delta = 2.0 * (activations[-1] - y) / y.size
    grads: list[Layer] = []
    for index in range(len(layers) - 1, -1, -1):
        weights = layers[index][0]
        below = activations[index]
        grads.append((below.T @ delta + 2.0 * penalty * weights, delta.sum(axis=0)))
        if index:
            delta = (delta @ weights.T) * (1.0 - below**2)
    return grads[::-1]


def _train(
    layers: list[Layer], x: np.ndarray, y: np.ndarray, settings: NeuralSettings
) -> list[Layer]:
    """``layers`` after ``settings.epochs`` steps of full-batch Adam."""
    params = [array for layer in layers for array in layer]
    first = [np.zeros_like(p) for p in params]
    second = [np.zeros_like(p) for p in params]
    beta1, beta2 = ADAM_DECAY
    for epoch in range(1, settings.epochs + 1):
        current = list(zip(params[::2], params[1::2]))
        grads = [
            g for layer in _gradients(current, x, y, settings.penalty) for g in layer
        ]
        rate = settings.learning_rate * np.sqrt(1 - beta2**epoch) / (1 - beta1**epoch)
        for i, grad in enumerate(grads):
            first[i] = beta1 * first[i] + (1 - beta1) * grad
            second[i] = beta2 * second[i] + (1 - beta2) * grad**2
            params[i] = params[i] - rate * first[i] / (
                np.sqrt(second[i]) + ADAM_EPSILON
            )
    return list(zip(params[::2], params[1::2]))


@dataclass(eq=False)
class NeuralEmulator(Emulator):
    """An ensemble of small networks over the unit cube.

    Attributes:
        members: every network's layers.
        names: the outputs.
        center: the outputs' training means.
        scale: the outputs' training standard deviations.
        space: the space whose unit cube the inputs are, if known.
    """

    members: list[list[Layer]]
    names: list[str]
    center: np.ndarray
    scale: np.ndarray
    space: ScenarioSpace | None = field(default=None)

    @classmethod
    def fit(
        cls,
        units: np.ndarray,
        values: np.ndarray,
        names: Sequence[str] | None = None,
        *,
        space: ScenarioSpace | None = None,
        settings: NeuralSettings | None = None,
    ) -> NeuralEmulator:
        """Train ``settings.members`` networks on ``units`` and the columns of ``values``."""
        settings = settings or NeuralSettings()
        x = 2.0 * np.atleast_2d(np.asarray(units, float)) - 1.0
        values = as_columns(values)
        center, scale = values.mean(axis=0), values.std(axis=0)
        scale = np.where(scale > 0, scale, 1.0)
        y = (values - center) / scale
        sizes = [x.shape[1], *settings.hidden, y.shape[1]]
        members = []
        for member in range(settings.members):
            seeds = np.random.SeedSequence(settings.seed, spawn_key=(member,))
            start = _initial(sizes, np.random.default_rng(seeds))
            members.append(_train(start, x, y, settings))
        names = output_names(values.shape[1], names)
        return cls(members, names, center, scale, space)

    def predict(self, units: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The ensemble's mean and spread (standard deviation), ``[point, output]``."""
        x = 2.0 * np.atleast_2d(np.asarray(units, float)) - 1.0
        outputs = np.stack([_forward(layers, x)[-1] for layers in self.members])
        mean, sd = outputs.mean(axis=0), outputs.std(axis=0)
        return self.center + self.scale * mean, self.scale * sd

    def _subset(self, index: int) -> NeuralEmulator:
        """The emulator of the output in column ``index`` (the last layers sliced)."""
        members = [
            [*layers[:-1], (layers[-1][0][:, [index]], layers[-1][1][[index]])]
            for layers in self.members
        ]
        return NeuralEmulator(
            members,
            [self.names[index]],
            self.center[[index]],
            self.scale[[index]],
            self.space,
        )
