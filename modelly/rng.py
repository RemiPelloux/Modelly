"""A faster ``random.Random`` with the standard library's exact streams.

``random.Random`` implements ``randint``, ``choice``, ``shuffle`` and ``sample``
in Python, and each draw goes through ``_randbelow`` as a separate method
call plus argument validation. In an agent-based model those four calls run
millions of times per experiment. ``FastRandom`` reimplements them with the
rejection loop written inline, making the same ``getrandbits`` calls in the
same order, so for a given seed it produces exactly the same numbers as
``random.Random``; a run seeded with either is reproducible with the other.
"""

from __future__ import annotations

import random
from collections.abc import MutableSequence, Sequence
from math import ceil, log
from operator import index
from typing import Any

SMALL_SET_SIZE = 21  # size of a small set minus size of an empty list (stdlib)
SAMPLE_SET_THRESHOLD = 5  # stdlib switches to a selection set above this k


class FastRandom(random.Random):
    """``random.Random`` with the hot draws inlined; identical streams."""

    def randint(self, a: int, b: int) -> int:
        """Return a random integer in [a, b], like ``random.randint``."""
        a = index(a)
        n = index(b) - a + 1
        if n <= 0:
            raise ValueError(f"empty range in randint({a}, {b})")
        k = n.bit_length()
        getrandbits = self.getrandbits
        r = getrandbits(k)
        while r >= n:
            r = getrandbits(k)
        return a + r

    def choice(self, seq: Sequence[Any]) -> Any:
        """Return a random element of ``seq``, like ``random.choice``."""
        n = len(seq)
        if not n:
            raise IndexError("Cannot choose from an empty sequence")
        k = n.bit_length()
        getrandbits = self.getrandbits
        r = getrandbits(k)
        while r >= n:
            r = getrandbits(k)
        return seq[r]

    def shuffle(self, x: MutableSequence[Any]) -> None:
        """Shuffle ``x`` in place, like ``random.shuffle`` (same stream)."""
        getrandbits = self.getrandbits
        for i in range(len(x) - 1, 0, -1):
            n = i + 1
            k = n.bit_length()
            j = getrandbits(k)
            while j >= n:
                j = getrandbits(k)
            x[i], x[j] = x[j], x[i]

    def sample(self, population: Sequence[Any], k: int, *, counts=None) -> list:
        """Return ``k`` unique elements of ``population``, like ``random.sample``."""
        if counts is not None:
            return super().sample(population, k, counts=counts)
        if not isinstance(population, Sequence):
            raise TypeError(
                "Population must be a sequence.  For dicts or sets, use sorted(d)."
            )
        n = len(population)
        if not 0 <= k <= n:
            raise ValueError("Sample larger than population or is negative")
        getrandbits = self.getrandbits
        result = [None] * k
        setsize = SMALL_SET_SIZE
        if k > SAMPLE_SET_THRESHOLD:
            setsize += 4 ** ceil(log(k * 3, 4))
        if n <= setsize:
            pool = list(population)
            for i in range(k):
                m = n - i
                kb = m.bit_length()
                j = getrandbits(kb)
                while j >= m:
                    j = getrandbits(kb)
                result[i] = pool[j]
                pool[j] = pool[m - 1]
            return result
        selected: set[int] = set()
        kb = n.bit_length()
        for i in range(k):
            j = getrandbits(kb)
            while j >= n or j in selected:
                j = getrandbits(kb)
            selected.add(j)
            result[i] = population[j]
        return result
