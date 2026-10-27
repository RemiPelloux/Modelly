"""Random streams keyed by (seed, stream) that give the same numbers on every backend.

A :class:`PhiloxStream` holds no generator state, only a count of the draws
made so far. Draw number ``call`` of stream ``stream`` gives element ``i`` the
Philox4x32-10 block at counter ``(i // k, sub, call, stream)`` and key
``seed``, where ``k`` elements share one 128-bit block. So the numbers depend
on the element's position only, not on the device, the batch it is drawn in
or the order of evaluation::

    stream = PhiloxStream(seed=42, stream=0, backend="cupy")
    alive = stream.bernoulli(survival)              # one draw per element
    draws = stream.draws()                          # one draw, in batches
    first, rest = draws.random(1000), draws.random(500, start=1000)

Uniforms are float64 with 53 random bits (two words, as numpy builds them) or
float32 with 24 (one word); bounded integers are ``high * word >> 32``, which
is exact and the same on every backend, with a bias below ``high / 2**32``.
Limits per draw: ``2**32`` blocks, so about 8.6 billion float64 uniforms.
"""

from __future__ import annotations

from typing import Any

from modelly.gpu.backend import Backend, get_backend
from modelly.gpu.binomial import binomial
from modelly.gpu.philox import WORD_BITS, WORD_MASK, WORDS, mulhilo_narrow, mulhilo_wide

FLOAT64_HIGH_SHIFT, FLOAT64_LOW_SHIFT = 5, 6  # 27 + 26 = 53 bits, numpy's construction
FLOAT64_HIGH_SCALE = 2.0**26
FLOAT64_SCALE = 2.0**-53
FLOAT32_SHIFT = 8  # 24 bits
FLOAT32_SCALE = 2.0**-24
DOUBLE_WORDS = 2


class PhiloxDraw:
    """One draw of a stream: elements addressed by position, drawable in batches."""

    def __init__(self, stream: PhiloxStream, call: int) -> None:
        """Bind the stream and this draw's number."""
        self.stream = stream
        self.call = call

    @property
    def backend(self) -> Backend:
        """The stream's backend."""
        return self.stream.backend

    def words(self, n: int, start: int = 0, per_element: int = 1, sub: int = 0):
        """``per_element`` uint32 words for each of ``n`` elements from ``start``: (n, k)."""
        xp, per_block = self.backend.xp, WORDS // per_element
        if n <= 0:
            return xp.zeros((0, per_element), dtype=xp.uint32)
        first, last = start // per_block, (start + n - 1) // per_block
        block = xp.arange(first, last + 1, dtype=xp.uint32)
        counter = (sub, self.call, self.stream.stream)
        outputs = self.backend.philox(block, counter, self.stream.key)
        words = xp.stack(outputs, axis=1).reshape(-1, per_element)
        offset = start - first * per_block
        return words[offset : offset + n]

    def words_at(self, positions: Any, per_element: int = 1, sub: int = 0):
        """The words ``words`` gives the elements at ``positions`` (any order): (n, k)."""
        xp, per_block = self.backend.xp, WORDS // per_element
        positions = xp.asarray(positions, dtype=xp.uint32)
        counter = (sub, self.call, self.stream.stream)
        outputs = self.backend.philox(positions // per_block, counter, self.stream.key)
        words = xp.stack(outputs, axis=1)
        lane = ((positions % per_block) * per_element)[:, None].astype(xp.int32)
        columns = [
            xp.take_along_axis(words, lane + j, axis=1) for j in range(per_element)
        ]
        return xp.concatenate(columns, axis=1)

    def _range(self, n: int, start: int) -> Any:
        """The positions ``start, ..., start + n - 1`` as uint32 (for the fused kernels)."""
        xp = self.backend.xp
        return xp.arange(start, start + n, dtype=xp.uint32)

    def bits(self, n: int, start: int = 0, sub: int = 0):
        """``n`` uniform uint32 words."""
        if self.backend.fused:
            counter = (sub, self.call, self.stream.stream)
            return self.backend.bits_at(self._range(n, start), counter, self.stream.key)
        return self.words(n, start, 1, sub)[:, 0]

    def random(self, n: int, start: int = 0, dtype: Any = None, sub: int = 0):
        """``n`` uniforms in [0, 1); float64 unless ``dtype`` or the backend says float32."""
        single = self._single(dtype)
        if self.backend.fused:
            return self.random_at(self._range(n, start), dtype, sub)
        return self._uniform(self.words(n, start, 1 if single else DOUBLE_WORDS, sub))

    def random_at(self, positions: Any, dtype: Any = None, sub: int = 0):
        """The uniforms ``random`` gives the elements at ``positions``."""
        single = self._single(dtype)
        if self.backend.fused:
            counter = (sub, self.call, self.stream.stream)
            return self.backend.uniform_at(positions, counter, self.stream.key, single)
        per_element = 1 if single else DOUBLE_WORDS
        return self._uniform(self.words_at(positions, per_element, sub))

    def _single(self, dtype: Any) -> bool:
        """Whether uniforms of ``dtype`` (None: the backend's float) are float32."""
        xp = self.backend.xp
        dtype = self.backend.float_dtype if dtype is None else dtype
        return xp.dtype(dtype) == xp.dtype(xp.float32)

    def _uniform(self, words: Any):
        """Uniforms from one word (float32, 24 bits) or two (float64, 53 bits) per row."""
        xp = self.backend.xp
        if words.shape[1] == 1:
            word = words[:, 0] >> FLOAT32_SHIFT
            return word.astype(xp.float32) * xp.float32(FLOAT32_SCALE)
        high = (words[:, 0] >> FLOAT64_HIGH_SHIFT).astype(xp.float64)
        low = (words[:, 1] >> FLOAT64_LOW_SHIFT).astype(xp.float64)
        return (high * FLOAT64_HIGH_SCALE + low) * FLOAT64_SCALE

    def integers(self, high: Any, n: int | None = None, start: int = 0, sub: int = 0):
        """Integers in ``[0, high)``, ``high`` a scalar or one bound per element (< 2**32)."""
        xp = self.backend.xp
        bound = xp.asarray(high, dtype=xp.uint32)
        n = int(bound.shape[0]) if n is None else n
        if self.backend.fused:
            counter = (sub, self.call, self.stream.stream)
            positions, key = self._range(n, start), self.stream.key
            return self.backend.bounded_at(positions, bound, counter, key)
        mulhilo = mulhilo_wide if self.backend.wide else mulhilo_narrow
        upper, _ = mulhilo(self.bits(n, start, sub), bound, xp)
        return upper.astype(self.backend.int_dtype)

    def binomial(self, count: Any, p: Any, start: int = 0):
        """One Binomial(count, p) variate per element (see ``modelly.gpu.binomial``)."""
        return binomial(self, count, p, start)


class PhiloxStream:
    """Counter-based random numbers for one (seed, stream) pair, on one backend.

    Args:
        seed: a non-negative integer below 2**64, the Philox key.
        stream: the stream number below 2**32; streams of one seed are independent.
        backend: a backend or backend name (see ``get_backend``).
    """

    def __init__(self, seed: int, stream: int = 0, backend: Any = None) -> None:
        """Key the stream; no number is drawn yet."""
        if seed < 0 or seed >> (2 * WORD_BITS) or stream < 0 or stream > WORD_MASK:
            raise ValueError("seed must be in [0, 2**64) and stream in [0, 2**32)")
        self.seed, self.stream = int(seed), int(stream)
        self.key = (self.seed & WORD_MASK, self.seed >> WORD_BITS)
        self.backend = get_backend(backend)
        self.calls = 0

    def draws(self) -> PhiloxDraw:
        """The next draw, for drawing one quantity in batches or by position."""
        draw = PhiloxDraw(self, self.calls)
        self.calls += 1
        return draw

    def random(self, n: int, dtype: Any = None):
        """``n`` uniforms in [0, 1)."""
        return self.draws().random(n, dtype=dtype)

    def integers(self, high: Any, n: int | None = None):
        """Integers in ``[0, high)``, one per element of ``high`` (or ``n`` of them)."""
        return self.draws().integers(high, n)

    def bernoulli(self, p: Any, n: int | None = None):
        """``n`` (or one per element of ``p``) booleans, True with probability ``p``."""
        p = self.backend.xp.asarray(p)
        n = int(p.shape[0]) if n is None else n
        return (
            self.draws().random(n, dtype=p.dtype if p.dtype.kind == "f" else None) < p
        )

    def binomial(self, count: Any, p: Any):
        """One Binomial(count, p) variate per element of ``count``."""
        return self.draws().binomial(count, p)

    def spawn(self, stream: int) -> PhiloxStream:
        """Stream ``stream`` of the same seed and backend, at its first draw."""
        return PhiloxStream(self.seed, stream, self.backend)

    def __getstate__(self) -> dict[str, Any]:
        """The seed, stream, draw count and backend name (devices do not pickle)."""
        return {**vars(self), "backend": self.backend.name}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Reload the backend by name."""
        self.__dict__.update(state)
        self.backend = get_backend(state["backend"])

    def __repr__(self) -> str:
        """Seed, stream, draws so far and backend."""
        return (
            f"<PhiloxStream seed={self.seed} stream={self.stream} "
            f"calls={self.calls} on {self.backend.name}>"
        )
