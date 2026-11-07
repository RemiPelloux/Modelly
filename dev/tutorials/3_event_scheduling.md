# Event Scheduling & Time

**Important:**

- If you are just exploring Modelly and want the fastest way to execute the code we recommend executing this tutorial online in a Colab notebook. [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/RemiPelloux/Modelly/blob/main/docs/tutorials/3_event_scheduling.ipynb) or if you do not have a Google account you can use [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/RemiPelloux/Modelly/main?labpath=docs%2Ftutorials%2F3_event_scheduling.ipynb) (This can take 30 seconds to 5 minutes to load)
- If you are running locally, please ensure you have the latest Modelly version installed.

## Tutorial Description

In the previous tutorials, you created agents, queried them with AgentSet, and learned activation patterns. In this tutorial, we cover **time** — how Modelly models progress through time, how you run simulations, and how to schedule events that happen at specific moments. By the end of this tutorial you will know how to:

- Understand how `model.time` advances during a simulation
- Run models with `run_for()` and `run_until()`
- Schedule one-off events at absolute or relative times
- Schedule recurring events with `Schedule`
- Control event priority
- Cancel events and stop recurring generators
- Combine step-based agent activation with discrete events in a single model

### IN COLAB? - Run the next cell

### Import Dependencies

```ipython3
import numpy as np

import modelly
from modelly.time import Priority, Schedule
```

## How Time Works in Modelly

Modelly models track simulation time with:

- **`model.time`** — A float representing the current simulation time (starts at 0.0).

### The default step mechanism

When you define a `step()` method on your model and advance time, Modelly wraps your step in an internal event system. Each step:

1. Advances `model.time` by 1.0
1. Executes your `step()` method For event-driven simulations, prefer these methods:

- **`model.run_for(n)`** — Advance time by `n` units (executing `n` steps for standard models)
- **`model.run_until(t)`** — Advance time until `model.time` reaches `t` These methods are the primary way to run any Modelly model.

### A quick example

```ipython3
class SimpleModel(modelly.Model):
    def __init__(self):
        super().__init__()
        self.step_count = 0

    def step(self):
        self.step_count += 1
        print(f"  Step {self.step_count} at time {self.time:.1f}")

model = SimpleModel()
print("Initial state:")
print(f"  step_count={model.step_count}, time={model.time}")
print("\nRunning for 3 time units:")
model.run_for(3)
print(f"\nFinal state: step_count={model.step_count}, time={model.time}")
```

```myst-ansi
Initial state:
  step_count=0, time=0.0

Running for 3 time units:
  Step 1 at time 1.0
  Step 2 at time 2.0
  Step 3 at time 3.0

Final state: step_count=3, time=3.0
```

Notice that after `run_for(3)`, both the example’s `step_count` and `time` are at 3. For standard step-based models, a user-defined step counter like this advances in lockstep with time. But as we’ll see, events can fire at *any* time — including between steps.

## `run_for` vs `run_until`

Both methods advance time and process any scheduled events (including the default step events) along the way. The difference is simple:

- `run_for(duration)` advances time by the specified **duration** from the current time
- `run_until(end_time)` advances time to the specified **absolute time**

```ipython3
model = SimpleModel()

print("run_for(2):")
model.run_for(2)
print(f"  → time is now {model.time}\n")

print("run_until(5):")
model.run_until(5)
print(f"  → time is now {model.time}\n")

print("run_for(3) more:")
model.run_for(3)
print(f"  → time is now {model.time}")
```

```myst-ansi
run_for(2):
  Step 1 at time 1.0
  Step 2 at time 2.0
  → time is now 2.0

run_until(5):
  Step 3 at time 3.0
  Step 4 at time 4.0
  Step 5 at time 5.0
  → time is now 5

run_for(3) more:
  Step 6 at time 6.0
  Step 7 at time 7.0
  Step 8 at time 8.0
  → time is now 8
```

`run_until` is particularly useful when you have a fixed end time for your simulation, or when coordinating with external time references:

```python
model.run_until(365)  # Run for one simulated year
```

## Scheduling One-Off Events

Beyond the regular step cycle, Modelly lets you schedule **events** — functions that execute at specific times. This is useful for modeling things that don’t happen every step: policy changes, natural disasters, market shocks, seasonal effects, or any occurrence that happens at a specific point in time. Use `model.schedule_event()` to schedule a one-off event:

- **`at=`** — Schedule at an **absolute** time
- **`after=`** — Schedule at a **relative** time from now (i.e., `model.time + after`) You must specify exactly one of `at` or `after`.

```ipython3
class EconomyModel(modelly.Model):
    """A simple economy where a tax reform happens at a specific time."""

    def __init__(self, n=50):
        super().__init__()
        self.tax_rate = 0.1
        self.events_log = []

        # Create agents with wealth
        for _ in range(n):
            a = modelly.Agent(self)
            a.wealth = 10

        # Schedule a tax reform at time 5.0
        self.schedule_event(self.tax_reform, at=5.0)

        # Schedule a stimulus check 2 time units from now (so at time 2.0)
        self.schedule_event(self.stimulus, after=2.0)

    def tax_reform(self):
        self.tax_rate = 0.25
        self.events_log.append(
            f"t={self.time:.1f}: Tax reform! Rate now {self.tax_rate}"
        )

    def stimulus(self):
        for agent in self.agents:
            agent.wealth += 5
        self.events_log.append(f"t={self.time:.1f}: Stimulus! Everyone gets 5 units")

    def step(self):
        # Simple taxation each step
        for agent in self.agents:
            tax = int(agent.wealth * self.tax_rate)
            agent.wealth -= tax

model = EconomyModel(10)
model.run_for(7)

print("Events that occurred:")
for event in model.events_log:
    print(f"  {event}")

print(f"\nFinal tax rate: {model.tax_rate}")
avg_wealth = model.agents.agg("wealth", np.mean)
print(f"Average wealth: {avg_wealth:.1f}")
```

```myst-ansi
Events that occurred:
  t=2.0: Stimulus! Everyone gets 5 units
  t=5.0: Tax reform! Rate now 0.25

Final tax rate: 0.25
Average wealth: 7.0
```

**Key point:** Events fire *during* time advancement. When `run_for(7)` processes time, it encounters the stimulus event at t=2.0 and the tax reform at t=5.0, executing them at the correct moments. Your `step()` method also fires at t=1.0, 2.0, 3.0, etc. as scheduled events under the hood.

### Canceling events

`schedule_event` returns an `Event` object. You can cancel it before it fires:

```ipython3
class CancelDemo(modelly.Model):
    def __init__(self):
        super().__init__()

        # Schedule two events
        self.event_a = self.schedule_event(self.event_a_fn, at=3.0)
        self.event_b = self.schedule_event(self.event_b_fn, at=5.0)

        # Cancel event B before it fires
        self.event_b.cancel()

    def event_a_fn(self):
        print(f"  Event A fired at t={self.time:.1f}")

    def event_b_fn(self):
        print(f"  Event B fired at t={self.time:.1f}")

    def step(self):
        pass

model = CancelDemo()
print("Running — Event B was canceled:")
model.run_for(6)
print("  (Event B never fired)")
```

```myst-ansi
Running — Event B was canceled:
  Event A fired at t=3.0
  (Event B never fired)
```

Cancellation is useful when model conditions change. For example, you might schedule a disaster event but cancel it if agents take preventive action.

## Scheduling Recurring Events

Many models have things that happen repeatedly but not every step — quarterly reports, seasonal cycles, periodic inspections, or interest payments. Use `model.schedule_recurring()` with a `Schedule` to define these patterns. The `Schedule` dataclass specifies:

- **`interval`** — Time between executions (required)
- **`start`** — When to begin (default: current time + interval)
- **`end`** — When to stop (default: never)
- **`count`** — Maximum number of executions (default: unlimited)

```ipython3
class SeasonalModel(modelly.Model):
    """A model with regular seasonal events."""

    def __init__(self, n=20):
        super().__init__()
        self.season = "spring"
        self.season_log = []

        for _ in range(n):
            a = modelly.Agent(self)
            a.wealth = 10

        # Change season every 3 time units, starting at t=3.0
        self.schedule_recurring(
            self.change_season,
            Schedule(interval=3.0),
        )

        # Collect taxes every 5 time units, but only 4 times
        self.schedule_recurring(
            self.collect_taxes,
            Schedule(interval=5.0, count=4),
        )

    def change_season(self):
        seasons = ["spring", "summer", "autumn", "winter"]
        idx = seasons.index(self.season)
        self.season = seasons[(idx + 1) % 4]
        self.season_log.append(f"t={self.time:.1f}: Season → {self.season}")

    def collect_taxes(self):
        for agent in self.agents:
            agent.wealth -= 1
        self.season_log.append(f"t={self.time:.1f}: Taxes collected!")

    def step(self):
        # Normal step — agents earn money
        for agent in self.agents:
            agent.wealth += self.random.randint(0, 2)

model = SeasonalModel(10)
model.run_for(20)

print("Timeline:")
for entry in model.season_log:
    print(f"  {entry}")
print(f"\nFinal season: {model.season}")
print(f"Average wealth: {model.agents.agg('wealth', np.mean):.1f}")
```

```myst-ansi
Timeline:
  t=3.0: Season → summer
  t=5.0: Taxes collected!
  t=6.0: Season → autumn
  t=9.0: Season → winter
  t=10.0: Taxes collected!
  t=12.0: Season → spring
  t=15.0: Taxes collected!
  t=15.0: Season → summer
  t=18.0: Season → autumn
  t=20.0: Taxes collected!

Final season: autumn
Average wealth: 27.6
```

### Controlling when recurring events start

By default, a recurring event first fires at `current_time + interval`. You can override this with the `start` parameter:

```ipython3
class StartDemo(modelly.Model):
    def __init__(self):
        super().__init__()

        # Fires at t=5, t=10, t=15, ... (default start)
        self.schedule_recurring(
            self.default_start_event,
            Schedule(interval=5.0),
        )

        # Fires at t=0, t=5, t=10, ... (start immediately)
        self.schedule_recurring(
            self.start_at_zero_event,
            Schedule(interval=5.0, start=0.0),
        )

        # Fires at t=2, t=7, t=12, ... (custom start)
        self.schedule_recurring(
            self.start_at_two_event,
            Schedule(interval=5.0, start=2.0),
        )

    def default_start_event(self):
        print(f"  Default start: t={self.time:.1f}")

    def start_at_zero_event(self):
        print(f"  Start at 0:    t={self.time:.1f}")

    def start_at_two_event(self):
        print(f"  Start at 2:    t={self.time:.1f}")

    def step(self):
        pass

model = StartDemo()
print("Events firing during first 12 time units:")
model.run_for(12)
```

```myst-ansi
Events firing during first 12 time units:
  Start at 0:    t=0.0
  Start at 2:    t=2.0
  Default start: t=5.0
  Start at 0:    t=5.0
  Start at 2:    t=7.0
  Default start: t=10.0
  Start at 0:    t=10.0
  Start at 2:    t=12.0
```

### Stopping recurring events

`schedule_recurring` returns an `EventGenerator` that you can stop at any time:

```ipython3
class StopDemo(modelly.Model):
    def __init__(self):
        super().__init__()
        self.counter = 0

        # Start a recurring event
        self.ticker = self.schedule_recurring(
            self.tick,
            Schedule(interval=1.0),
        )

    def tick(self):
        self.counter += 1
        print(f"  Tick #{self.counter} at t={self.time:.1f}")

    def step(self):
        # Stop the ticker after 5 ticks
        if self.counter >= 5 and self.ticker.is_active:
            self.ticker.stop()
            print(f"  Ticker stopped at t={self.time:.1f}")

model = StopDemo()
model.run_for(10)
print(f"\nTotal ticks: {model.counter}")
```

```myst-ansi
  Tick #1 at t=1.0
  Tick #2 at t=2.0
  Tick #3 at t=3.0
  Tick #4 at t=4.0
  Tick #5 at t=5.0
  Ticker stopped at t=6.0

Total ticks: 5
```

### Using `end` and `count` for automatic limits

Instead of manually stopping a generator, you can set limits in the `Schedule` itself:

```python
# Stop after time 50.0
Schedule(interval=5.0, end=50.0)
# Execute at most 10 times
Schedule(interval=5.0, count=10)
# Both: stop after 10 executions OR after time 50.0, whichever comes first
Schedule(interval=5.0, count=10, end=50.0)
```

### Dynamic intervals

The `interval` parameter can be a callable that returns the next interval dynamically. The callable receives the model as its argument. This is useful for modeling processes where the frequency changes over time:

```ipython3
class AcceleratingModel(modelly.Model):
    """A model where events happen faster and faster."""

    def __init__(self):
        super().__init__()
        self.event_times = []

        # Interval starts at 4.0 and shrinks each time
        self.schedule_recurring(
            self.record_event,
            Schedule(
                interval=lambda m: max(1.0, 4.0 - m.time * 0.3),
                count=8,
            ),
        )

    def record_event(self):
        self.event_times.append(self.time)

    def step(self):
        pass

model = AcceleratingModel()
model.run_for(25)

print("Event times (accelerating intervals):")
for i, t in enumerate(model.event_times):
    if i > 0:
        gap = t - model.event_times[i - 1]
        print(f"  t={t:.1f} (gap: {gap:.1f})")
    else:
        print(f"  t={t:.1f}")
```

```myst-ansi
Event times (accelerating intervals):
  t=4.0
  t=6.8 (gap: 2.8)
  t=8.8 (gap: 2.0)
  t=10.1 (gap: 1.4)
  t=11.1 (gap: 1.0)
  t=12.1 (gap: 1.0)
  t=13.1 (gap: 1.0)
  t=14.1 (gap: 1.0)
```

## Event Priority

When multiple events are scheduled for the same time, **priority** determines execution order. Modelly provides three priority levels:

- `Priority.HIGH` (1) — Executes first
- `Priority.DEFAULT` (5) — Normal priority
- `Priority.LOW` (10) — Executes last Lower numeric values mean higher priority. Note that the default model `step()` is scheduled at `Priority.HIGH`, so it runs before your custom events at the same time.

```ipython3
class PriorityDemo(modelly.Model):
    def __init__(self):
        super().__init__()

        # Schedule three events at the same time with different priorities
        self.schedule_event(
            self.low_priority_event,
            at=2.0,
            priority=Priority.LOW,
        )
        self.schedule_event(
            self.high_priority_event,
            at=2.0,
            priority=Priority.HIGH,
        )
        self.schedule_event(
            self.default_priority_event,
            at=2.0,
            priority=Priority.DEFAULT,
        )

    def low_priority_event(self):
        print(f"  LOW priority event at t={self.time:.1f}")

    def high_priority_event(self):
        print(f"  HIGH priority event at t={self.time:.1f}")

    def default_priority_event(self):
        print(f"  DEFAULT priority event at t={self.time:.1f}")

    def step(self):
        if self.time == 2.0:
            print(f"  Model step (HIGH priority) at t={self.time:.1f}")

model = PriorityDemo()
print("Events at t=2.0 in execution order:")
model.run_for(3)
```

```myst-ansi
Events at t=2.0 in execution order:
  HIGH priority event at t=2.0
  Model step (HIGH priority) at t=2.0
  DEFAULT priority event at t=2.0
  LOW priority event at t=2.0
```

Priority is useful when the order of operations matters. For example, you might want data collection (HIGH) to happen before agent actions (DEFAULT), or environmental updates (LOW) to happen after everything else.

## Putting It All Together: A Complete Example

Let’s build a more complete model that combines step-based agent activation with discrete events. This is a simple economy where:

- Agents exchange money every step (standard activation)
- A central bank adjusts interest rates every 10 time units (recurring event)
- A one-time economic stimulus happens at t=25 (one-off event)
- The simulation runs until t=50

```ipython3
class Citizen(modelly.Agent):
    def __init__(self, model):
        super().__init__(model)
        self.wealth = 10
        self.savings = 0

    def exchange(self):
        """Give 1 unit to a random other agent."""
        if self.wealth > 0:
            others = [agent for agent in self.model.agents if agent is not self]
            if others:
                other = self.random.choice(others)
                other.wealth += 1
                self.wealth -= 1

    def earn_interest(self):
        """Earn interest on savings based on current rate."""
        interest = int(self.savings * self.model.interest_rate)
        self.savings += interest

class CentralBankModel(modelly.Model):
    """An economy with monetary policy events."""

    def __init__(self, n_citizens=50):
        super().__init__()
        self.interest_rate = 0.05
        self.log = []

        Citizen.create_agents(model=self, n=n_citizens)

        # Distribute initial savings randomly
        for agent in self.agents:
            agent.savings = self.random.randint(0, 20)

        # Recurring: Central bank reviews interest rate every 10 time units
        self.rate_review = self.schedule_recurring(
            self.review_interest_rate,
            Schedule(interval=10.0, start=10.0),
        )

        # Recurring: Interest is paid every 5 time units
        self.schedule_recurring(
            self.pay_interest,
            Schedule(interval=5.0),
        )

        # One-off: Economic stimulus at t=25
        self.schedule_event(self.economic_stimulus, at=25.0)

    def review_interest_rate(self):
        """Central bank adjusts rate based on average wealth."""
        avg_wealth = self.agents.agg("wealth", np.mean)
        if avg_wealth < 8:
            self.interest_rate = min(0.15, self.interest_rate + 0.02)
            action = "raised"
        elif avg_wealth > 12:
            self.interest_rate = max(0.01, self.interest_rate - 0.02)
            action = "lowered"
        else:
            action = "held"
        self.log.append(
            f"t={self.time:5.1f} | Rate review: {action} to {self.interest_rate:.0%} "
            f"(avg wealth: {avg_wealth:.1f})"
        )

    def pay_interest(self):
        """Pay interest to all citizens."""
        total_paid = 0
        for agent in self.agents:
            interest = int(agent.savings * self.interest_rate)
            agent.savings += interest
            total_paid += interest
        self.log.append(f"t={self.time:5.1f} | Interest paid: {total_paid} total")

    def economic_stimulus(self):
        """One-time stimulus: every citizen gets 5 units."""
        for agent in self.agents:
            agent.wealth += 5
        self.log.append(f"t={self.time:5.1f} | *** STIMULUS: +5 to all citizens ***")

    def step(self):
        """Regular step: agents exchange money."""
        self.agents.shuffle_do("exchange")

        # Some agents save a portion of their wealth
        for agent in self.agents.select(lambda a: a.wealth > 3):
            save_amount = agent.wealth // 4
            agent.wealth -= save_amount
            agent.savings += save_amount

# Run the simulation
model = CentralBankModel(50)
model.run_until(50)

print("=== Central Bank Economy: Event Log ===\n")
for entry in model.log:
    print(f"  {entry}")

print(f"\n=== Final State (t={model.time:.0f}) ===")
print(f"Interest rate: {model.interest_rate:.0%}")
print(f"Avg wealth: {model.agents.agg('wealth', np.mean):.1f}")
print(f"Avg savings: {model.agents.agg('savings', np.mean):.1f}")
total = sum(a.wealth + a.savings for a in model.agents)
print(f"Total money in economy: {total}")
```

```myst-ansi
=== Central Bank Economy: Event Log ===

  t=  5.0 | Interest paid: 17 total
  t= 10.0 | Rate review: raised to 7% (avg wealth: 2.1)
  t= 10.0 | Interest paid: 41 total
  t= 15.0 | Interest paid: 41 total
  t= 20.0 | Rate review: raised to 9% (avg wealth: 1.3)
  t= 20.0 | Interest paid: 65 total
  t= 25.0 | *** STIMULUS: +5 to all citizens ***
  t= 25.0 | Interest paid: 70 total
  t= 30.0 | Rate review: raised to 11% (avg wealth: 2.6)
  t= 30.0 | Interest paid: 124 total
  t= 35.0 | Interest paid: 142 total
  t= 40.0 | Rate review: raised to 13% (avg wealth: 1.2)
  t= 40.0 | Interest paid: 194 total
  t= 45.0 | Interest paid: 227 total
  t= 50.0 | Rate review: raised to 15% (avg wealth: 1.0)
  t= 50.0 | Interest paid: 300 total

=== Final State (t=50) ===
Interest rate: 15%
Avg wealth: 1.0
Avg savings: 48.8
Total money in economy: 2490
```

This model demonstrates the core Modelly pattern: the `step()` method handles regular per-step agent activation, while `schedule_event` and `schedule_recurring` handle things that happen at specific times or on different schedules. The event system manages all timing automatically — you just specify *what* should happen and *when*.

## When to Use Events vs Steps

Use case

Approach

Agents act every time unit

step() with agents.shuffle_do()

Something happens once at a known time

schedule_event(fn, at=...)

Something happens repeatedly on a schedule

schedule_recurring(fn, Schedule(...))

Something happens after a delay from now

schedule_event(fn, after=...)

Different processes run at different frequencies

Combine step + recurring events

Pure discrete-event simulation (no regular steps)

Use only schedule_event / schedule_recurring

The step mechanism itself is implemented as a recurring event under the hood (with

Priority.HIGH, interval 1.0, starting at t=1.0). This means steps and custom events

coexist naturally in the same time-ordered event queue.

## Summary

**Running models:**

- `model.run_for(n)` — Advance time by `n` units
- `model.run_until(t)` — Advance time to absolute time `t` **One-off events:**
- `model.schedule_event(fn, at=t)` — Fire at absolute time `t`
- `model.schedule_event(fn, after=d)` — Fire `d` time units from now
- `event.cancel()` — Cancel before it fires **Recurring events:**
- `model.schedule_recurring(fn, Schedule(interval=...))` — Repeat on a schedule
- `Schedule(interval, start, end, count)` — Control timing, limits
- `generator.stop()` — Stop a recurring event
- `generator.is_active` — Check if still running **Priority:** `Priority.HIGH` → `Priority.DEFAULT` → `Priority.LOW` **Time tracking:** `model.time` (float), plus any user-defined counters you maintain in your model

## Next Steps

Check out the [adding space tutorial](https://remipelloux.github.io/Modelly/dev/tutorials/4_adding_space.html) on how to add a space to your Modelly model.
