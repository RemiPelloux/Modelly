"""Collection schedule for one dataset: interval, time window and sliding window."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DatasetConfig:
    """Configuration for dataset collection behavior.

    Attributes:
        interval: Collection frequency in time units
        start_time: First time to begin collection
        end_time: Last time to collect (None = collect forever)
        window_size: Max snapshots to keep (None = keep all, N = sliding window)
        enabled: Whether collection is active
        _next_collection: Next scheduled collection time (internal)

    Examples:
        # Collect every step from 0 to infinity
        DatasetConfig(interval=1, start_time=0)

        # Collect every 5 steps from 100 to 500
        DatasetConfig(interval=5, start_time=100, end_time=500)

        # Collect every step, keep only last 1000 snapshots
        DatasetConfig(interval=1, start_time=0, window_size=1000)

        # Warmup phase: skip first 100 steps, collect 100-200
        DatasetConfig(interval=1, start_time=100, end_time=200)
    """

    interval: int | float = 1
    start_time: int | float = 0
    end_time: int | float | None = None
    window_size: int | None = None
    enabled: bool = True
    _next_collection: int | float = 0
    _last_collection: int | float = -1

    def __post_init__(self):
        """Validate configuration."""
        if self.interval <= 0:
            raise ValueError(f"interval must be > 0, got {self.interval}")
        if self.start_time < 0:
            raise ValueError(f"start_time must be >= 0, got {self.start_time}")
        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be > start_time ({self.start_time})"
            )
        if self.window_size is not None and self.window_size <= 0:
            raise ValueError(f"window_size must be > 0 or None, got {self.window_size}")

        self._next_collection = self.start_time

    def should_collect(self, current_time: float) -> bool:
        """Check if we should collect at this time.

        Args:
            current_time: The current simulation time

        Returns:
            True if collection should happen, False otherwise
        """
        if not self.enabled:
            return False

        # Before start time
        if current_time < self.start_time:
            return False

        # After end time
        if self.end_time is not None and current_time > self.end_time:
            return False

        # Not at scheduled time
        return not current_time < self._next_collection

    def update_next_collection(self, current_time: float) -> None:
        """Update the next collection time.

        Args:
            current_time: The current simulation time
        """
        self._next_collection = current_time + self.interval

        # Auto-disable if we've passed end_time
        if self.end_time is not None and self._next_collection > self.end_time:
            self.enabled = False
