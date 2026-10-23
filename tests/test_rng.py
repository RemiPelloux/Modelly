"""FastRandom must reproduce random.Random's streams exactly."""

import os
import random

import pytest

from modelly import FastRandom, Model
from modelly.rng import NATIVE, PyFastRandom

IMPLEMENTATIONS = (
    [FastRandom] if FastRandom is PyFastRandom else [FastRandom, PyFastRandom]
)


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


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
@pytest.mark.parametrize("seed", [0, 1, 42, 2**40, "a string seed"])
def test_streams_are_identical(impl, seed):
    """Same seed, same draws, in the same order."""
    assert _drive(impl(seed)) == _drive(random.Random(seed))


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_errors_match_the_stdlib(impl):
    """Edge cases raise the same exceptions."""
    fast, ref = impl(1), random.Random(1)
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


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_shuffle_matches_stdlib_across_run_boundaries(impl):
    """Lists around every bit-length boundary shuffle exactly like random.Random."""
    sizes = [*range(140), 255, 256, 257, 1000, 3000, 4097, 5000]
    for size in sizes:
        for seed in (1, 2, 3):
            expected, actual = list(range(size)), list(range(size))
            reference, fast = random.Random(seed), impl(seed)
            reference.shuffle(expected)
            fast.shuffle(actual)
            assert actual == expected
            assert fast.random() == reference.random()


class _ListSubclass(list):
    """A list subclass: the compiled paths must hand it to the stdlib code."""


def _edge_drive(rng):
    """Arguments on both sides of every compiled fast path."""
    out = []
    items = list(range(40))
    for k in (0, 1, 5, 6, 7, 13, 40):  # set size changes above k = 5
        out.append(rng.sample(items, k))
        out.append(rng.sample(tuple(items), k))
        out.append(rng.sample(range(5000), k))
        out.append(rng.sample(items, k=k))
    out.append(rng.sample(list(range(10_000)), 6))  # selection-set path from a list
    out.append(rng.choice(tuple("abc")))
    out.append(rng.choice(range(7, 70)))
    out.append(rng.choice(_ListSubclass([1, 2, 3])))
    seq = _ListSubclass(range(30))
    rng.shuffle(seq)
    out.append(list(seq))
    out.extend(
        (rng.randint(-(2**40), 2**40), rng.randint(True, 5), rng.randint(-5, -1))
    )
    out.append(rng.randint(0, 2**32 - 1))
    out.append(rng.randint(0, 2**32))
    out.append(rng._randbelow(2**33))
    state = rng.getstate()
    first = [rng.randint(0, 9) for _ in range(5)]
    rng.setstate(state)
    out.append(first == [rng.randint(0, 9) for _ in range(5)])
    out.append(rng.gauss(0.0, 1.0))
    return out


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
@pytest.mark.parametrize("seed", [3, 2**64 + 1])
def test_edges_of_the_fast_paths_match_the_stdlib(impl, seed):
    """Fast paths and their fallbacks draw exactly what random.Random draws."""
    assert _edge_drive(impl(seed)) == _edge_drive(random.Random(seed))


def test_the_compiled_core_is_used_when_built():
    """Where the extension is built, FastRandom is the compiled class."""
    if os.environ.get("MODELLY_PURE_PYTHON"):
        pytest.skip("pure Python forced")
    try:
        from modelly._native import fastrng  # noqa: F401, PLC0415
    except ImportError:
        pytest.skip("compiled core not built for this interpreter")
    assert NATIVE
    assert FastRandom is not PyFastRandom
