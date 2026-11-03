"""The ordering rule of docs/event_ordering.md: time, then priority, then insertion order."""

import pytest

from modelly import Model
from modelly.time.events.event import Priority


class Clock(Model):
    """A model that logs its steps and its events."""

    def __init__(self):
        """An empty log."""
        super().__init__(rng=1)
        self.log = []

    def step(self):
        """Log the step."""
        self.log.append(("step", self.time))

    def default(self):
        """Log a default-priority event."""
        self.log.append(("default", self.time))

    def again(self):
        """Log a second default-priority event."""
        self.log.append(("default again", self.time))

    def high(self):
        """Log a high-priority event."""
        self.log.append(("high", self.time))

    def low(self):
        """Log a low-priority event."""
        self.log.append(("low", self.time))

    def between(self):
        """Log an event between two steps."""
        self.log.append(("between", self.time))


def test_time_then_priority_then_insertion_order():
    """Each rule of the page, and the step's place among the events."""
    model = Clock()
    model.schedule_event(model.default, at=2)
    model.schedule_event(model.high, at=2, priority=Priority.HIGH)
    model.schedule_event(model.low, at=2, priority=Priority.LOW)
    model.schedule_event(model.again, at=2)
    model.schedule_event(model.between, at=1.5)
    model.run_for(3)
    assert [name for name, _ in model.log] == [
        "step", "between", "high", "step", "default", "default again", "low", "step",
    ]  # fmt: skip


def test_a_high_event_scheduled_after_the_step_was_runs_after_it():
    """The step at time 2 is scheduled when the step at time 1 runs: insertion order decides."""
    model = Clock()
    model.run_for(1)
    model.schedule_event(model.high, at=2, priority=Priority.HIGH)
    model.run_for(1)
    assert [name for name, _ in model.log] == ["step", "step", "high"]


@pytest.mark.parametrize("resume", [False, True])
def test_the_order_survives_a_checkpoint(tmp_path, resume):
    """Saved with events pending and loaded, the run logs the same order."""
    model = Clock()
    model.schedule_event(model.low, at=2, priority=Priority.LOW)
    model.schedule_event(model.default, at=2)
    model.run_for(1)
    if resume:
        model.save(tmp_path / "clock.ckpt")
        model = Clock.load(tmp_path / "clock.ckpt")
    model.run_for(2)
    assert [name for name, _ in model.log] == ["step", "step", "default", "low", "step"]
