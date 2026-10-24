"""Threshold descriptor: fire a callback when a ContinuousState crosses a limit."""

from __future__ import annotations

import contextlib
import math
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.time.signals import Observable, ObservableSignals
from modelly.time.signals.core import BaseObservable

if TYPE_CHECKING:
    from modelly.behaviour.states.state import ContinuousState
    from modelly.core.agent import Agent


def _crossing_roots(
    v: float, a: float, current_value: float, limit: float
) -> list[tuple[float, float]]:
    """Return (time, crossing velocity) pairs where the trajectory meets the limit.

    Solves the intersection root using 0.5*a*t^2 + v*t + (x0 - limit) = 0.
    """
    if a == 0.0:
        return _linear_root(v, current_value, limit)
    return _quadratic_roots(v, a, current_value, limit)


def _linear_root(
    v: float, current_value: float, limit: float
) -> list[tuple[float, float]]:
    """Return the non-negative root of the pure linear case, if any."""
    valid_times = []
    if v != 0.0:
        t = (limit - current_value) / v
        if t >= 0.0:
            valid_times.append((t, v))
    return valid_times


def _quadratic_roots(
    v: float, a: float, current_value: float, limit: float
) -> list[tuple[float, float]]:
    """Return the non-negative roots of the quadratic case with their velocities."""
    valid_times = []
    qa = 0.5 * a
    qb = v
    qc = current_value - limit
    discriminant = qb**2 - 4 * qa * qc

    # Allow microscopic negative discriminants due to float inaccuracies near tangent touches
    if discriminant >= -np.finfo(float).eps:
        disc = max(0.0, discriminant)
        sqrt_disc = math.sqrt(disc)

        t1 = (-qb - sqrt_disc) / (2 * qa)
        t2 = (-qb + sqrt_disc) / (2 * qa)

        for t in (t1, t2):
            if t >= -np.finfo(float).eps:
                t_clean = max(0.0, t)
                # Calculate exact velocity at the moment of intersection: v(t) = v0 + a*t
                v_cross = qb + a * t_clean
                valid_times.append((t_clean, v_cross))
    return valid_times


class Threshold:
    """Class-level descriptor that fires a callback when a ContinuousState crosses a limit.

    The limit may be a fixed float or an Observable attribute on the agent.
    When the limit is an Observable, the threshold recalculates automatically
    whenever the limit changes -- no imperative re-arming calls needed.
    """

    def __init__(
        self,
        state: ContinuousState,
        limit: float | Observable,
        callback: str,
        direction: str = "crossing",
    ) -> None:
        """Initialize the Threshold descriptor.

        Args:
            state: The ContinuousState descriptor to monitor.
            limit: The crossing value, either a fixed float or an Observable
                on the agent. When an Observable, the projected crossing time
                updates automatically whenever the limit changes.
            callback: Name of the agent method to call when the limit is crossed.
            direction: The boundary direction constraint ("rising", "falling", or "crossing").
        """
        self.state = state
        self.limit = limit
        self.callback = callback
        self.direction = direction

    def __set_name__(self, owner: type, name: str) -> None:
        """Bind the descriptor and register it to the class blueprint."""
        self.public_name = name
        self.time_attr = f"_{name}_projected_time"
        self.event_attr = f"_{name}_event"

        if "_continuous_thresholds" not in owner.__dict__:
            owner._continuous_thresholds = []
        if name not in owner._continuous_thresholds:
            owner._continuous_thresholds.append(name)

    def _resolve_limit(self, instance: Agent) -> float:
        """Return the current limit value for this instance.

        If the limit is an Observable descriptor, reads its current value
        from the instance. Otherwise returns the fixed float.
        """
        if isinstance(self.limit, BaseObservable):
            return self.limit.__get__(instance, type(instance))
        return self.limit

    def bind(self, instance: Agent) -> None:
        """Wire up this threshold for the instance via the signal bus.

        Subscribes to CHANGED signals from both the watched ContinuousState
        and, when the limit is an Observable, from the limit itself -- so
        the projected crossing time updates automatically whenever either changes.

        Args:
            instance (Agent): The instance to bind to.
        """
        if hasattr(instance, f"_{self.public_name}_recalc"):
            return

        setattr(instance, self.time_attr, math.inf)
        setattr(instance, self.event_attr, None)

        def _recalc(message: Any = None, _inst: Agent = instance) -> None:
            self.recalculate(_inst)

        def _trigger(_inst: Agent = instance) -> None:
            self.execute(_inst)

        # Strong references to prevent weakref event queue from silently dropping them
        setattr(instance, f"_{self.public_name}_recalc", _recalc)
        setattr(instance, f"_{self.public_name}_trigger", _trigger)

        instance.observe(self.state.public_name, ObservableSignals.CHANGED, _recalc)

        if isinstance(self.limit, BaseObservable):
            instance.observe(self.limit.public_name, ObservableSignals.CHANGED, _recalc)

        self.recalculate(instance)

    def __get__(self, instance: Agent, owner: type | None = None) -> Any:
        """Retrieve the projected crossing time."""
        if instance is None:
            return self
        return getattr(instance, self.time_attr, math.inf)

    def recalculate(self, instance: Agent) -> None:
        """Compute and cache the exact crossing time using quadratic extrapolation.

        Solves the intersection root using 0.5*a*t^2 + v*t + (x0 - limit) = 0.
        """
        state_dict = self.state._get_state(instance)
        self.state._refresh_rate_if_dirty(state_dict, instance)
        v = state_dict["current_rate"]
        a = state_dict["second_order_rate"]

        current_value = self.state.__get__(instance)
        limit = self._resolve_limit(instance)

        valid_times = _crossing_roots(v, a, current_value, limit)
        future_crossings = self._future_crossings(valid_times, current_value, limit)

        if not future_crossings:
            self._never_crosses(instance)
        else:
            self._schedule_crossing(instance, min(future_crossings))

    def _future_crossings(
        self, valid_times: list[tuple[float, float]], current_value: float, limit: float
    ) -> list[float]:
        """Keep the root times that match the direction and are not a re-fire."""
        future_crossings = []
        for t, v_cross in valid_times:
            if self.direction == "rising" and v_cross <= 0:
                continue
            if self.direction == "falling" and v_cross >= 0:
                continue
            if self.direction == "crossing" and v_cross == 0:
                # Tangent touches bounce away rather than crossing the boundary.
                continue

            # Reject a zero-time root where the state is already sitting exactly
            # at the limit. This occurs mid-callback when the callback changes
            # the rate (e.g. brake() sets acceleration=-3.0 while position==limit),
            # causing recalculate() to find t=0 as a valid root. Scheduling an
            # event at model.time+0 would immediately re-fire the same threshold.
            if t == 0.0 and math.isclose(
                current_value,
                limit,
                rel_tol=0,
                abs_tol=np.finfo(float).eps * abs(limit or 1.0),
            ):
                continue

            future_crossings.append(t)
        return future_crossings

    def _schedule_crossing(self, instance: Agent, time_to_cross: float) -> None:
        """Record the projected crossing time and (re)schedule its trigger event."""
        projected_time = instance.model.time + time_to_cross
        setattr(instance, self.time_attr, projected_time)

        # Cancel any previously tracked native event for this threshold
        old_event = getattr(instance, self.event_attr, None)
        if old_event is not None:
            with contextlib.suppress(Exception):
                old_event.cancel()

        # Retrieve the trigger
        trigger_func = getattr(instance, f"_{self.public_name}_trigger")
        new_event = instance.model.schedule_event(trigger_func, at=projected_time)
        setattr(instance, self.event_attr, new_event)

    def _never_crosses(self, instance: Agent) -> None:
        """Mark this threshold as having no future crossing and stop tracking it."""
        setattr(instance, self.time_attr, math.inf)

        old_event = getattr(instance, self.event_attr, None)
        if old_event is not None:
            with contextlib.suppress(Exception):
                old_event.cancel()

        setattr(instance, self.event_attr, None)

    def execute(self, instance: Agent) -> None:
        """Fire the callback when a crossing is reached.

        Args:
            instance (Agent): The instance whose threshold was triggered.
        """
        setattr(instance, self.time_attr, math.inf)
        setattr(instance, self.event_attr, None)

        callback_method = getattr(instance, self.callback)
        callback_method()
