"""``solve_batch`` against ``scipy.integrate.solve_ivp`` on one ODE per agent.

    python benchmarks/ode/compare.py                       # 10 to 100,000 agents
    python benchmarks/ode/compare.py --agents 1000 10000 --repeats 5

The workload is the target-cell-limited model of influenza within a host (Baccam et al.,
2006), three equations per agent, in two populations: ``alike``, whose parameters vary by
10% between agents, and ``diverse``, whose infection rate, virus production and initial
virus span one to four orders of magnitude, so the agents' infections peak at different
times and need small steps at different moments. Three ways to integrate it over ten days,
all with the Dormand-Prince pair (``RK45``) at the same tolerances:

* ``loop``: ``solve_ivp`` once per agent (each agent with its own steps and error control);
* ``stacked``: every agent in one ``solve_ivp`` system (one step size for all, error measured
  as the RMS over every agent);
* ``batch``: ``modelly.couple.solve_batch`` (each agent's own steps, one array pass per stage).

Time is the best of ``--repeats`` wall-clock runs (one run for the loop past 1,000 agents; the
loop is skipped past ``--loop-max``). Accuracy is each agent's error against a reference
solved at ``rtol=1e-12``, in units of its own tolerance ``atol + rtol |y|``: the largest over
agents, so 1 means the worst agent is exactly at the tolerance asked for. Results go to
``results.json`` next to this file.

Reference:
    Baccam, P., Beauchemin, C., Macken, C. A., Hayden, F. G. and Perelson, A. S. (2006).
    Kinetics of influenza A virus infection in humans. Journal of Virology, 80(15), 7590-7599.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

import numpy as np
import scipy
from scipy.integrate import solve_ivp

from modelly.couple import solve_batch

HERE = Path(__file__).resolve().parent
SPAN = (0.0, 10.0)
RTOL, ATOL = 1e-6, 1e-9
REFERENCE = {"rtol": 1e-12, "atol": 1e-14}
LONG_LOOP = 1000


def viral(t, y, p):
    """Target cells infected by virus become infected cells, which make virus."""
    cells, infected, virus = y[0], y[1], y[2]
    infection = p["beta"] * cells * virus
    return np.array(
        [
            -infection,
            infection - p["delta"] * infected,
            p["p"] * infected - p["c"] * virus,
        ]
    )


def population(
    agents: int, kind: str = "alike", seed: int = 1
) -> tuple[np.ndarray, dict]:
    """Initial states (all target cells healthy) and per-agent parameters."""
    rng = np.random.default_rng(seed)

    def spread(low: float, high: float) -> np.ndarray:
        if kind == "alike":
            return np.sqrt(low * high) * rng.uniform(0.9, 1.1, agents)
        return np.exp(rng.uniform(np.log(low), np.log(high), agents))

    params = {"beta": spread(2.0, 40.0), "p": spread(5.0, 50.0), "delta": spread(1.0, 4.0),
              "c": 3.0}  # fmt: skip
    virus = spread(1e-6, 1e-2)
    return np.vstack([np.ones(agents), np.zeros(agents), virus]), params


def loop(y0, params):
    """``solve_ivp`` once per agent."""
    out = np.empty_like(y0)
    for j in range(y0.shape[1]):
        own = {k: v[j] if np.ndim(v) else v for k, v in params.items()}
        out[:, j] = solve_ivp(
            viral, SPAN, y0[:, j], rtol=RTOL, atol=ATOL, args=(own,)
        ).y[:, -1]
    return out


def stacked(y0, params):
    """Every agent in one ``solve_ivp`` system."""
    m, k = y0.shape

    def fun(t, flat):
        return viral(t, flat.reshape(m, k), params).ravel()

    return solve_ivp(fun, SPAN, y0.ravel(), rtol=RTOL, atol=ATOL).y[:, -1].reshape(m, k)


def batch(y0, params):
    """``modelly.couple.solve_batch``."""
    return solve_batch(viral, SPAN, y0, params, rtol=RTOL, atol=ATOL).y


def best_time(fn, y0, params, repeats: int) -> tuple[float, np.ndarray]:
    """The fastest of ``repeats`` runs, and the answer."""
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn(y0, params)
        times.append(time.perf_counter() - start)
    return min(times), result


def error_in_tolerances(y: np.ndarray, reference: np.ndarray) -> float:
    """The worst agent's error, in units of its own tolerance (RMS over its equations)."""
    scaled = (y - reference) / (ATOL + RTOL * np.abs(reference))
    return float(np.sqrt(np.mean(scaled**2, axis=0)).max())


def measure(agents: int, kind: str, repeats: int, loop_max: int) -> dict:
    """Time and accuracy of each way at one population size."""
    y0, params = population(agents, kind)
    reference = solve_batch(viral, SPAN, y0, params, **REFERENCE).y
    row = {"population": kind, "agents": agents}
    ways = {"loop": loop, "stacked": stacked, "batch": batch}
    for name, fn in ways.items():
        if name == "loop" and agents > loop_max:
            continue
        runs = 1 if name == "loop" and agents > LONG_LOOP else repeats
        seconds, y = best_time(fn, y0, params, runs)
        row[name] = {
            "seconds": seconds,
            "worst_error": error_in_tolerances(y, reference),
        }
    return row


def main() -> None:
    """Measure every size, print a table and write ``results.json``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--agents", type=int, nargs="+", default=[10, 100, 1000, 10000, 100000]
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--loop-max", type=int, default=10000)
    options = parser.parse_args()
    solve_batch(viral, SPAN, *population(2))  # import scipy and warm up before timing
    rows = []
    for kind in ("alike", "diverse"):
        for agents in options.agents:
            rows.append(measure(agents, kind, options.repeats, options.loop_max))
            print(json.dumps(rows[-1]))
    load = [round(x, 1) for x in os.getloadavg()] if hasattr(os, "getloadavg") else None
    meta = {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "machine": platform.processor() or platform.machine(),
            "rtol": RTOL, "atol": ATOL, "span": SPAN, "load_at_end": load}  # fmt: skip
    (HERE / "results.json").write_text(
        json.dumps({"meta": meta, "rows": rows}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
