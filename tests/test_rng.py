"""FastRandom must reproduce random.Random's streams exactly."""

import random

import pytest

from modelly import FastRandom, Model


def _drive(rng):
    """A mixed workload of draws; returns everything drawn so streams can be compared."""
    out = []
    for i in range(1, 60):
        out.append(rng.randint(-3, i))
        out.append(rng.randint(0, 2**i))
        seq = list(range(i + 1))
        out.append(rng.choice(seq))
        rng.shuffle(seq)
        out.append(tuple(seq))
        out.append(tuple(rng.sample(seq, k=min(i, 4))))  # the pool path
        out.append(
            tuple(rng.sample(range(i * 50), k=min(i, 12)))
        )  # the selection-set path
        out.append(rng.random())
        out.append(rng.randrange(1, i + 2))
    out.append(tuple(rng.sample(range(10), k=0)))
    out.append(tuple(rng.sample(["a", "b"], k=5, counts=[3, 2])))
    return out


@pytest.mark.parametrize("seed", [0, 1, 42, 2**40, "a string seed"])
def test_streams_are_identical(seed):
    """Same seed, same draws, in the same order."""
    assert _drive(FastRandom(seed)) == _drive(random.Random(seed))


def test_errors_match_the_stdlib():
    """Edge cases raise the same exceptions."""
    fast, ref = FastRandom(1), random.Random(1)
    with pytest.raises(ValueError):
        fast.randint(3, 2)
    with pytest.raises(IndexError):
        fast.choice([])
    with pytest.raises(ValueError):
        fast.sample([1, 2], 3)
    with pytest.raises(TypeError):
        fast.sample({1, 2}, 1)
    assert fast.randint(5, 5) == ref.randint(5, 5) == 5
    assert fast.sample([7], 1) == [7]


def test_model_random_is_a_fast_random_with_the_same_stream():
    """The model's stdlib generator is a FastRandom seeded as before."""
    model = Model(rng=7)
    assert isinstance(model.random, FastRandom)
    assert isinstance(model.random, random.Random)
    reference = random.Random(model.scenario._stdlib_seed)
    assert [model.random.randint(0, 99) for _ in range(20)] == [
        reference.randint(0, 99) for _ in range(20)
    ]
