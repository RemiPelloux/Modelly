# Event ordering

What runs first when several things are due at the same time. Modelly orders every event, the model’s steps included, by three keys, in this order:

1. **Time.** An earlier event runs first.
1. **Priority.** At the same time, the lower priority value runs first: `Priority.HIGH` (1), then `Priority.DEFAULT` (5), then `Priority.LOW` (10). A model’s `step` is scheduled at `Priority.HIGH`.
1. **Insertion order.** At the same time and priority, the event scheduled first runs first.

```python
from modelly import Model
from modelly.time import Priority

class Clock(Model):
    def step(self):
        print("step", self.time)

    def default(self):
        print("default", self.time)

    def high(self):
        print("high", self.time)

model = Clock(rng=1)
model.schedule_event(model.default, at=2)
model.schedule_event(model.high, at=2, priority=Priority.HIGH)
model.run_for(3)
```

Events hold their function by a weak reference, so schedule a method or a module-level function, not a lambda that nothing else keeps.

At time 2 this runs `high` (HIGH, scheduled before the step at time 2 was), then `step` (HIGH, scheduled when the step at time 1 ran), then `default`. The step at time 2 is scheduled when the step at time 1 runs, so an event scheduled at HIGH priority before then runs before it, and one scheduled at HIGH priority after it runs after it.

This is the rule Modelly 2.0 keeps (epic H4 of its [roadmap](https://remipelloux.github.io/Modelly/dev/roadmap/2.0.0.html)): no model’s order changes in 2.0, so there is nothing to warn about (see [Deprecations](https://remipelloux.github.io/Modelly/dev/deprecations.html)). `tests/test_event_ordering.py` checks each rule.

The order is the same in the compiled and the pure-Python schedulers, after a checkpoint is loaded, and on every platform, since it uses no wall-clock time and no object identity.
