"""One day of the within-host zoo model at its epidemic peak: AgentODE against a solve_ivp loop.

Runs the model (100,000 hosts by default) to day 20, then integrates the next day twice from
the same state: once with the model's AgentODE (every host in one batch) and once with one
``solve_ivp`` call per exposed host, same method and tolerances. Prints the two times and
the worst difference in units of the tolerance, and writes ``within_host.json``.

    python benchmarks/ode/within_host.py [hosts]
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from modelly.zoo.within_host.model import STATE, Host, WithinHost, WithinHostScenario

DAYS_BEFORE = 20
HERE = Path(__file__).resolve().parent


def loop(model, y0, start):
    """One ``solve_ivp`` call per exposed host over one day."""
    s, table = model.scenario, model.columns[Host]
    rhs = model.ode.rhs
    out = y0.copy()
    for j in np.flatnonzero(table.exposed):
        params = {"beta": table.beta[j]}
        fun = lambda t, y, p=params: rhs(t, y, p)  # noqa: E731
        ref = solve_ivp(fun, (start, start + 1.0), y0[:, j], rtol=s.rtol, atol=s.atol)
        out[:, j] = ref.y[:, -1]
    return out


def main(hosts: int) -> dict:
    """Time both, compare, return the record."""
    model = WithinHost(WithinHostScenario(rng=1, hosts=hosts))
    model.run(DAYS_BEFORE)
    table = model.columns[Host]
    y0 = np.array([table[name] for name in STATE])
    start = float(model.time)
    tic = time.perf_counter()
    expected = loop(model, y0, start)
    looped = time.perf_counter() - tic
    tic = time.perf_counter()
    model.ode.advance(start, 1.0)
    batched = time.perf_counter() - tic
    got = np.array([table[name] for name in STATE])
    s = model.scenario
    scale = s.atol + s.rtol * np.abs(expected)
    return {
        "hosts": hosts, "exposed": int(table.exposed.sum()), "day": start,
        "loop_seconds": looped, "batch_seconds": batched, "speedup": looped / batched,
        "worst_error_in_tolerances": float(np.max(np.abs(got - expected) / scale)),
        "load": os.getloadavg()[0] if hasattr(os, "getloadavg") else None,
    }  # fmt: skip


if __name__ == "__main__":
    record = main(int(sys.argv[1]) if len(sys.argv) > 1 else 100_000)
    (HERE / "within_host.json").write_text(json.dumps(record, indent=2) + "\n")
    sys.stdout.write(json.dumps(record, indent=2) + "\n")
