"""Tests for ``modelly studio``: the command line, the checks before serving, the server."""

import importlib.util
import json
import os
import threading

import pytest

from modelly.studio import __main__ as cli
from modelly.studio.config import ENV_VAR, StudioConfig

WOLF_SHEEP = "modelly.examples.advanced.wolf_sheep.model:WolfSheep"

BROKEN = """\
from modelly import Model


class Broken(Model):
    def __init__(self, rng=None):
        raise RuntimeError("cannot build")
"""


def test_help_describes_the_panels(capsys):
    """--help lists the options, the panels and the exit codes."""
    with pytest.raises(SystemExit) as stop:
        cli.main(["--help"], prog="modelly studio")
    assert stop.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: modelly studio ")
    for word in (
        "--port",
        "--host",
        "--no-browser",
        "timeline",
        "profiler",
        "exit codes",
    ):
        assert word in out


def test_defaults_serve_on_localhost():
    """The server listens on 127.0.0.1 unless told otherwise."""
    args = cli.build_parser().parse_args(["x.py:M"])
    assert args.host == cli.LOCALHOST == "127.0.0.1"
    assert not args.no_browser


@pytest.mark.parametrize("port", ["-1", "70000", "nope"])
def test_bad_port_is_a_usage_error(port):
    """A port outside 0..65535 is refused."""
    with pytest.raises(SystemExit) as stop:
        cli.main(["x.py:M", "--port", port])
    assert stop.value.code == cli.EXIT_USAGE


def test_missing_target_is_a_usage_error(tmp_path, capsys):
    """A target that does not exist exits 2 before any server starts."""
    assert cli.main([str(tmp_path / "nope.py") + ":M"]) == cli.EXIT_USAGE
    assert "no such file" in capsys.readouterr().err


def test_a_model_that_raises_exits_1(tmp_path, capsys):
    """A model whose constructor raises exits 1 with the error."""
    pytest.importorskip("solara")
    path = tmp_path / "broken.py"
    path.write_text(BROKEN, encoding="utf-8")
    assert cli.main([f"{path}:Broken"]) == cli.EXIT_MODEL_ERROR
    assert "cannot build" in capsys.readouterr().err


def test_without_the_viz_extra(monkeypatch, capsys):
    """Without solara the command says which extra to install."""
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name == "solara" else real(name),
    )
    assert cli.main([WOLF_SHEEP]) == cli.EXIT_USAGE
    assert "modelly-abm[viz]" in capsys.readouterr().err


def test_main_serves_the_config(monkeypatch):
    """The command line becomes a StudioConfig, served on the port asked for."""
    pytest.importorskip("solara")
    served = {}
    monkeypatch.setattr(cli, "serve", lambda *args: served.update(args=args))
    argv = [WOLF_SHEEP, "--port", "0", "--no-browser", "--seed", "3", "--every", "5"]
    assert cli.main(argv) == cli.EXIT_OK
    config, host, port, browser = served["args"]
    assert config == StudioConfig(target=WOLF_SHEEP, seed=3, every=5)
    assert host == "127.0.0.1" and port > 0 and not browser


def test_the_input_options_reach_the_config():
    """--results, --observations and --analysis feed the new tabs; --help lists them."""
    argv = [WOLF_SHEEP, "--results", "runs", "--observations", "obs.csv"]
    argv += ["--analysis", "fit.py:results"]
    config = cli.config_from(cli.build_parser().parse_args(argv))
    assert (config.results, config.observations, config.analysis) == (
        "runs",
        "obs.csv",
        "fit.py:results",
    )
    assert StudioConfig.from_json(config.to_json()) == config
    text = cli.build_parser().format_help()
    for word in ("--results", "--observations", "--analysis", "map", "ensemble"):
        assert word in text


def test_serve_warns_when_assets_are_missing(monkeypatch, capsys):
    """A cache without Solara's front-end files is reported before serving."""
    uvicorn = pytest.importorskip("uvicorn")
    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    monkeypatch.setattr(cli.assets, "warning", lambda: "files are not cached\n")
    cli.serve(StudioConfig(target=WOLF_SHEEP), cli.LOCALHOST, 1234, browser=False)
    assert "files are not cached" in capsys.readouterr().err


def test_free_port_is_bindable():
    """free_port gives a port the OS reports as free."""
    assert 0 < cli.free_port(cli.LOCALHOST) <= cli.MAX_PORT


class FakeServer:
    """Stands in for uvicorn.Server."""

    def __init__(self, config=None):
        """Record the config."""
        self.config = config
        self.started = False
        self.should_exit = False
        self.ran = threading.Event()

    def run(self):
        """Pretend to serve."""
        self.started = True
        self.ran.set()


def test_open_when_ready_opens_the_browser(monkeypatch):
    """The default browser opens once the server has started."""
    opened = threading.Event()
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.set())
    server = FakeServer()
    cli.open_when_ready(server, "http://127.0.0.1:1")
    server.run()
    assert opened.wait(timeout=5)


def test_open_when_ready_gives_up_when_the_server_exits(monkeypatch):
    """No browser opens for a server that stopped before starting."""
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: pytest.fail("opened"))
    server = FakeServer()
    server.should_exit = True
    cli.open_when_ready(server, "http://127.0.0.1:1")


def test_serve_exports_the_config_and_runs_uvicorn(monkeypatch):
    """Serve hands the config to the app through the environment and runs uvicorn."""
    uvicorn = pytest.importorskip("uvicorn")
    made = []
    monkeypatch.setattr(
        uvicorn, "Server", lambda config: made.append(FakeServer(config)) or made[-1]
    )
    for name in (ENV_VAR, "SOLARA_APP", "SERVER_NAME", "SERVER_PORT"):
        monkeypatch.delenv(name, raising=False)
    config = StudioConfig(target=WOLF_SHEEP)
    cli.serve(config, cli.LOCALHOST, 1234, browser=False)
    assert made[0].ran.is_set()
    assert made[0].config.port == 1234 and made[0].config.host == cli.LOCALHOST
    assert json.loads(os.environ[ENV_VAR])["target"] == WOLF_SHEEP
    assert os.environ["SOLARA_APP"] == cli.APP
