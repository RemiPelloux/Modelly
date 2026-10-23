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

# n.bit_length() for every n below BITS_TABLE_SIZE. A tuple subscript is cheaper
# than the method call, and the ranges an ABM draws from are almost all small.
BITS_TABLE_SIZE = 4096
_BITS = tuple(n.bit_length() for n in range(BITS_TABLE_SIZE))
_SEQUENCE_TYPES = frozenset((list, tuple, range))
# Above this length shuffle walks the list in runs of constant bit length.
SEGMENTED_SHUFFLE_MIN = 64


class FastRandom(random.Random):
    """``random.Random`` with the hot draws inlined; identical streams."""

    def randint(self, a: int, b: int) -> int:
        """Return a random integer in [a, b], like ``random.randint``."""
        # ``type(x) is int`` is specialised by the interpreter; ``index`` is a call.
        if type(a) is not int or type(b) is not int:
            a = index(a)
            b = index(b)
        n = b - a + 1
        if 0 < n < BITS_TABLE_SIZE:
            k = _BITS[n]
        elif n <= 0:
            raise ValueError(f"empty range in randint({a}, {b})")
        else:
            k = n.bit_length()
        r = self.getrandbits(k)
        while r >= n:
            r = self.getrandbits(k)
        return a + r

    def choice(self, seq: Sequence[Any]) -> Any:
        """Return a random element of ``seq``, like ``random.choice``."""
        n = len(seq)
        if not n:
            raise IndexError("Cannot choose from an empty sequence")
        k = _BITS[n] if n < BITS_TABLE_SIZE else n.bit_length()
        r = self.getrandbits(k)
        while r >= n:
            r = self.getrandbits(k)
        return seq[r]

    def shuffle(self, x: MutableSequence[Any]) -> None:
        """Shuffle ``x`` in place, like ``random.shuffle`` (same stream)."""
        if len(x) > SEGMENTED_SHUFFLE_MIN:
            self._shuffle_segmented(x)
            return
        getrandbits = self.getrandbits
        bits = _BITS
        for i in range(len(x) - 1, 0, -1):
            n = i + 1
            k = bits[n] if n < BITS_TABLE_SIZE else n.bit_length()
            j = getrandbits(k)
            while j >= n:
                j = getrandbits(k)
            x[i], x[j] = x[j], x[i]

    def _shuffle_segmented(self, x: MutableSequence[Any]) -> None:
        """The Fisher-Yates loop of ``shuffle``, one run per bit length.

        Every ``n`` in ``[2**(k-1), 2**k - 1]`` has bit length ``k``, so within
        a run the draw width is constant and the per-element lookup goes away.
        The draws are the same ``getrandbits(k)`` calls in the same order.
        """
        getrandbits = self.getrandbits
        i = len(x) - 1
        while i > 0:
            k = (i + 1).bit_length()
            low = max(1 << (k - 1), 2) - 1  # smallest i of this run
            for m in range(i, low - 1, -1):
                n = m + 1
                j = getrandbits(k)
                while j >= n:
                    j = getrandbits(k)
                x[m], x[j] = x[j], x[m]
            i = low - 1

    def sample(self, population: Sequence[Any], k: int, *, counts=None) -> list:
        """Return ``k`` unique elements of ``population``, like ``random.sample``."""
        if counts is not None:
            return super().sample(population, k, counts=counts)
        # The ABC check costs several hundred ns; the common types skip it.
        if type(population) not in _SEQUENCE_TYPES and not isinstance(
            population, Sequence
        ):
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
                kb = _BITS[m] if m < BITS_TABLE_SIZE else m.bit_length()
                j = getrandbits(kb)
                while j >= m:
                    j = getrandbits(kb)
                result[i] = pool[j]
                pool[j] = pool[m - 1]
            return result
        selected: set[int] = set()
        kb = _BITS[n] if n < BITS_TABLE_SIZE else n.bit_length()
        for i in range(k):
            j = getrandbits(kb)
            while j >= n or j in selected:
                j = getrandbits(kb)
            selected.add(j)
            result[i] = population[j]
        return result
