# Time

`modelly.time` holds the event list, events and event generators, the scheduling methods of the
model, and signals (observables that notify subscribers when they change).

| Module | Contents |
|---|---|
| `modelly.time.events` | `Event`, `EventList`, `EventGenerator`, `Schedule`, `Priority` |
| `modelly.time.schedule` | `HasSchedule`: `step`, `run_for`, `run_until`, `schedule_event`, `schedule_recurring` on the model |
| `modelly.time.signals` | `Observable`, `HasEmitters`, `computed_property`, `ObservableList`, the signal types |

## Events

```{eval-rst}
.. automodule:: modelly.time.events.event
   :members:
```

```{eval-rst}
.. automodule:: modelly.time.events.event_list
   :members:
```

```{eval-rst}
.. automodule:: modelly.time.events.generator
   :members:
```

## Scheduling on the model

`Model` inherits these methods; they are also listed on the [Core](core.md) page.

```{eval-rst}
.. automodule:: modelly.time.schedule
   :members:
```

## Signals

`HasEmitters` takes its subscription methods (`observe`, `unobserve`, `observe_class`, ...)
from `modelly.time.signals.subscriptions`; they are listed under `HasEmitters`.

```{eval-rst}
.. automodule:: modelly.time.signals.core
   :members: BaseObservable, Observable, ComputedState, computed_property
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.time.signals.emitters
   :members:
   :inherited-members:
```

```{eval-rst}
.. automodule:: modelly.time.signals.computed
   :members:
```

```{eval-rst}
.. automodule:: modelly.time.signals.collections
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.time.signals.batching
   :members:
```

```{eval-rst}
.. automodule:: modelly.time.signals.types
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.time.signals.util
   :members:
```
