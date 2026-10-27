"""Tests for stream sources and observation operators (modelly.stream)."""

import json
import math
from types import SimpleNamespace

import pandas as pd
import pytest

from modelly.stream import (
    CSVSource,
    HTTPSource,
    Observation,
    ObservationOperator,
    ReplaySource,
)

RECORDS = [
    {"time": 2, "cases": 5},
    {"time": 1, "cases": 3, "deaths": 0},
    {"time": 3, "cases": 8},
]


def test_replay_hands_out_in_time_order_up_to_until():
    """Polls return due observations in order, each once."""
    source = ReplaySource(RECORDS)
    assert [o.time for o in source.poll(until=2)] == [1.0, 2.0]
    assert source.poll(until=2) == []
    rest = source.poll()
    assert [(o.time, dict(o.values)) for o in rest] == [(3.0, {"cases": 8.0})]


def test_replay_reads_a_dataframe_and_drops_empty_fields():
    """A DataFrame works like records; missing values are left out."""
    frame = pd.DataFrame({"time": [0, 1], "cases": [1.0, None]})
    first, second = ReplaySource(frame).poll()
    assert first.values == {"cases": 1.0}
    assert second.values == {}


def test_record_without_time_is_refused():
    """Every record needs its time field."""
    with pytest.raises(ValueError, match="time"):
        ReplaySource([{"cases": 1}])


def test_csv_source_follows_a_growing_file(tmp_path):
    """Rows appended between polls arrive on the next poll; half-written lines wait."""
    path = tmp_path / "cases.csv"
    source = CSVSource(path)
    assert source.poll() == []
    path.write_text("time,cases\n1,3\n2,5\n3,")
    assert [o.time for o in source.poll()] == [1.0, 2.0]
    with path.open("a") as handle:
        handle.write("8\n4,13\n")
    assert [(o.time, o.values["cases"]) for o in source.poll()] == [
        (3.0, 8.0),
        (4.0, 13.0),
    ]
    assert source.poll() == []


def test_http_source_keeps_only_new_records():
    """Each poll fetches the whole list again; records already seen are skipped."""
    pages = [RECORDS[:2], RECORDS]
    calls = []

    def fetch(url):
        calls.append(url)
        return json.dumps(pages[len(calls) - 1]).encode()

    source = HTTPSource("https://example.org/cases", fetch=fetch)
    assert [o.time for o in source.poll()] == [1.0, 2.0]
    assert [o.time for o in source.poll()] == [3.0]
    assert calls == ["https://example.org/cases"] * 2


def test_late_observation_is_dropped():
    """An observation older than one already handed out cannot be used any more."""
    pages = [[{"time": 5, "cases": 1}], [{"time": 4, "cases": 9}]]
    source = HTTPSource("u", fetch=lambda url: json.dumps(pages.pop(0)).encode())
    assert len(source.poll()) == 1
    assert source.poll() == []


MODEL = SimpleNamespace(cases=4, hospital=2)


def _operator():
    """Cases and hospital occupancy, read from attributes."""
    return ObservationOperator(cases=lambda m: m.cases, hospital=lambda m: m.hospital)


def test_operator_reads_every_quantity():
    """Calling an operator reads each quantity as a float, in order."""
    operator = _operator()
    assert operator(MODEL) == {"cases": 4.0, "hospital": 2.0}
    assert operator.names == ("cases", "hospital")


def test_residuals_cover_shared_quantities():
    """Residuals are observed minus modelled, only where the observation has a value."""
    observation = Observation(1.0, {"cases": 7.0, "deaths": 1.0})
    assert _operator().residuals(MODEL, observation) == {"cases": 3.0}


def test_log_likelihood_is_gaussian():
    """The score is the sum of independent normal log densities."""
    observation = Observation(1.0, {"cases": 7.0, "hospital": 2.0})
    expected = -0.5 * (math.log(2 * math.pi) + 2 * math.log(2) + (3 / 2) ** 2) - 0.5 * (
        math.log(2 * math.pi)
    )
    got = _operator().log_likelihood(
        MODEL, observation, {"cases": 2.0, "hospital": 1.0}
    )
    assert got == pytest.approx(expected)


def test_invalid_operators_and_scales_are_refused():
    """No quantity, a non-callable or a non-positive sd is an error."""
    with pytest.raises(ValueError, match="at least one"):
        ObservationOperator()
    with pytest.raises(TypeError, match="callables"):
        ObservationOperator(cases=3)
    with pytest.raises(ValueError, match="positive"):
        _operator().log_likelihood(MODEL, Observation(0.0, {"cases": 1.0}), 0)
