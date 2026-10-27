"""Per-agent random streams: each agent draws from generators of its own.

A model opts in with ``agent_streams = True`` on its class. ``agent.random`` and
``agent.rng`` then come from a seed derived from the model's seed and the
agent's stream key (its ``unique_id`` unless ``stream_key`` is overridden),
so an agent's draws do not depend on how many draws other agents made or on
the order in which agents step. This is what lets a population split across
processes give the same results as one process: an agent takes its stream
with it. Without the flag, every agent shares ``model.random`` and
``model.rng`` as before.

The seed of key ``k`` is ``SeedSequence(entropy, spawn_key=(*root, DOMAIN, k))``
where ``entropy`` and ``root`` are the scenario's seed sequence: replicates of a
scenario get different streams, and no stream equals one that
``SeedSequence.spawn`` hands out, since spawned keys never reach ``DOMAIN``.
The generators are created on an agent's first draw and travel with it in
checkpoints and pickles.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

import numpy as np

from modelly.core.rng import FastRandom

if TYPE_CHECKING:
    from modelly.core.agent import Agent

# Separates agent streams from the seeds SeedSequence.spawn derives ("MDLY").
STREAM_DOMAIN = 0x4D444C59
_RANDOM = "_stream_random"
_RNG = "_stream_rng"
# The instance attributes holding an agent's generators once it has drawn.
STREAM_ATTRIBUTES = (_RANDOM, _RNG)


def stream_seed(agent: Agent) -> np.random.SeedSequence:
    """The seed sequence of ``agent``'s own streams."""
    key = agent.stream_key()
    if type(key) is not int or key < 0:
        raise ValueError(
            f"stream_key() must return a non-negative int, got {key!r} "
            f"for {type(agent).__name__}"
        )
    root = agent.model.scenario.seed_sequence
    return np.random.SeedSequence(
        root.entropy, spawn_key=(*root.spawn_key, STREAM_DOMAIN, key)
    )


def own_random(agent: Agent) -> Random:
    """``agent``'s stdlib-compatible generator, created on first use."""
    try:
        return agent.__dict__[_RANDOM]
    except KeyError:
        seed = int(stream_seed(agent).generate_state(1, dtype=np.uint32)[0])
        generator = agent.__dict__[_RANDOM] = FastRandom(seed)
        return generator


def own_rng(agent: Agent) -> np.random.Generator:
    """``agent``'s numpy generator, of the scenario's bit generator, created on first use."""
    try:
        return agent.__dict__[_RNG]
    except KeyError:
        bit_generator = getattr(np.random, agent.model.scenario._generator_class)
        generator = agent.__dict__[_RNG] = np.random.Generator(
            bit_generator(stream_seed(agent))
        )
        return generator
