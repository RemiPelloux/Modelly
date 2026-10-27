"""Plain random designs: ``n`` points drawn uniformly over the parameter box.

``[design] kind = "uniform"`` with ``n = 20`` in an experiment file, or
``design_factory("uniform")(20)`` in Python, once the plugin is installed.
"""

from __future__ import annotations

from dataclasses import dataclass

from modelly.experiments.designs import Design


@dataclass
class Uniform(Design):
    """``n`` independent uniform points, the same for the same generator state."""

    n: int
    kind = "uniform"

    def points(self, space, rng=None):
        """``n`` points of ``space`` from the experiment's design stream ``rng``."""
        if not space.dimensions:
            return [space.complete({})]
        sample = rng.random((self.n, len(space.dimensions)))
        return [space.point(row) for row in sample]


def uniform(n: int) -> Uniform:
    """The factory the entry point names: ``n`` uniform points."""
    return Uniform(n)
