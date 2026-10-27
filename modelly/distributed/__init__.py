"""Distributed simulation: one model split across processes (provisional, 1.4).

This first part plans the split: ``partition.grid_blocks`` cuts a grid into
blocks with their halos, and ``Model.agent_streams`` gives every agent random
streams of its own, so a split run can draw what a single process draws. The
workers, halo exchange and migration follow.
"""

from modelly.distributed.partition import Block, BlockLayout, GridBlocks, grid_blocks

__all__ = ["Block", "BlockLayout", "GridBlocks", "grid_blocks"]
