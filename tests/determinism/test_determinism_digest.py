"""The canonical form behind run digests, and the ``python -m modelly.dev golden`` CLI."""

import enum
import math

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from modelly import Agent, Model
from modelly.dev import __main__ as dev_cli
from modelly.dev.digest import (
    DigestError,
    canonical,
    canonical_bytes,
    collected_data,
    digest,
)
from modelly.dev.golden import differences, read_golden, write_golden

DIGITS = 3
EXIT_PASSED, EXIT_FAILED, EXIT_USAGE = 0, 1, 2


class Colour(enum.Enum):  # noqa: D101
    RED = 1


def test_floats_are_written_exactly_or_rounded():
    """Exact hex by default; ``digits`` significant digits when asked; NaN is stable."""
    third = 1 / 3
    assert canonical(third) == "f:" + float.hex(third)
    assert canonical(third, DIGITS) == "f:3.33e-01"
    assert canonical(third, DIGITS) == canonical(third + 1e-12, DIGITS)
    assert canonical(math.nan, DIGITS) == canonical(math.nan)
    assert canonical(np.float64(0.5)) == canonical(0.5)


def test_one_spelling_per_value():
    """Containers, numpy, enums, bytes, sets and frames each have one canonical form."""
    assert canonical((1, [2, np.int64(3)])) == [1, [2, 3]]
    assert canonical(np.arange(2)) == [0, 1]
    assert canonical({3, 1, 2}) == canonical({2, 3, 1}) == [1, 2, 3]
    assert canonical({1: "a"}) == {"1": "a"}
    assert canonical(Colour.RED) == "RED"
    assert canonical(b"\x00\xff") == "b:00ff"
    frame = pd.DataFrame({"a": [1, 2]})
    assert canonical(frame) == {"columns": ["a"], "index": [0, 1], "data": [[1, 2]]}


def test_agents_and_graphs_by_identity_not_address():
    """Agents are written by unique_id; graphs as sorted nodes and edges."""
    model = Model(rng=1)
    agent = Agent(model)
    assert canonical(agent) == {"agent": agent.unique_id}
    graph = nx.Graph([(2, 1), (3, 2)])
    assert canonical(graph) == {"nodes": [1, 2, 3], "edges": [[1, 2], [2, 3]]}


def test_unknown_objects_are_refused():
    """An object whose only spelling is its repr cannot be digested."""
    with pytest.raises(DigestError, match="object"):
        canonical(object())


def test_bytes_are_compact_ascii_with_sorted_keys():
    """Key order and container type do not change the bytes or the digest."""
    assert canonical_bytes({"b": 1, "a": "é"}) == b'{"a":"\\u00e9","b":1}'
    assert digest({"a": [1], "b": 2}) == digest({"b": 2, "a": (1,)})
    assert len(digest(0)) == len("0" * 64)


def test_collected_data_without_a_collector():
    """A model with no datacollector contributes only its state."""
    assert collected_data(Model(rng=1)) == {}


def test_golden_file_round_trip_and_differences(tmp_path):
    """write_golden and read_golden agree; differences names missing and changed runs."""
    path = tmp_path / "golden.json"
    write_golden(path, {"boltzmann_wealth_model": "aa", "schelling": "bb"})
    assert read_golden(path) == {"boltzmann_wealth_model": "aa", "schelling": "bb"}
    found = differences({"schelling": "cc"}, read_golden(path))
    assert found == [
        "boltzmann_wealth_model: no golden digest (run golden --update)",
        "schelling: bb != golden cc",
    ]


def _fake_digests(monkeypatch, digests):
    monkeypatch.setattr(dev_cli, "current_digests", lambda exact=False: dict(digests))


def test_cli_update_check_and_json(monkeypatch, tmp_path, capsys):
    """--update writes the file, the check passes then fails on a change, --json prints."""
    path = tmp_path / "golden.json"
    _fake_digests(monkeypatch, {"schelling": "aa"})
    assert dev_cli.main(["golden", "--update", "--file", str(path)]) == EXIT_PASSED
    assert dev_cli.main(["golden", "--file", str(path)]) == EXIT_PASSED
    assert "1 golden digests match" in capsys.readouterr().out
    _fake_digests(monkeypatch, {"schelling": "bb"})
    assert dev_cli.main(["golden", "--file", str(path)]) == EXIT_FAILED
    assert "schelling: bb != golden aa" in capsys.readouterr().out
    assert dev_cli.main(["golden", "--json"]) == EXIT_PASSED
    assert capsys.readouterr().out == '{"schelling": "bb"}\n'


def test_cli_without_a_checkout_needs_a_file(monkeypatch, capsys):
    """Outside a source checkout the golden file must be named."""

    def no_checkout():
        raise dev_cli.GateError("not a checkout")

    _fake_digests(monkeypatch, {})
    monkeypatch.setattr(dev_cli, "checkout_root", no_checkout)
    assert dev_cli.main(["golden"]) == EXIT_USAGE
    assert "pass --file" in capsys.readouterr().err
