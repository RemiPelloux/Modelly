"""Command line for ``modelly studio``: serve Modelly Studio for a model on localhost.

Solara and its server are imported only once the command line is read, so ``--help``
works without the ``viz`` extra and the telemetry and version check are off before
Solara reads its settings.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import socket
import sys
import threading
import time
import warnings
import webbrowser

from modelly.profile.loader import TargetError
from modelly.studio.config import (
    DEFAULT_BUDGET_MIB,
    DEFAULT_EVERY,
    DEFAULT_PROFILE_STEPS,
    DEFAULT_SEED,
    StudioConfig,
)

EXIT_OK, EXIT_MODEL_ERROR, EXIT_USAGE = 0, 1, 2
PROG = "python -m modelly.studio"
GUIDE = "https://remipelloux.github.io/Modelly/studio.html"
LOCALHOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_PORT = 2**16 - 1
APP = "modelly.studio.app:Page"
SAMESITE_WARNING = "Cookies with samesite=none require https"
BROWSER_POLL_S = 0.1
# Solara settings, read from the environment when Solara is imported: no telemetry,
# the production server (no auto-reload). The server makes no version check either.
SOLARA_ENVIRONMENT = {
    "SOLARA_TELEMETRY_MIXPANEL_ENABLE": "False",
    "SOLARA_MODE": "production",
}

DESCRIPTION = """\
Open a model in Modelly Studio, a browser app to run it, change its parameters,
scrub back through the run and see the profiler, the linter and the plots side
by side. The server listens on 127.0.0.1 only, unless --host says otherwise, and
the default browser opens on it.

The parameter panel is built from the model's Scenario (and its constructor's
keyword arguments): sliders for fractions, number and text fields, selects for
Literal and Enum fields, checkboxes for booleans, and the seed. Each run is
recorded: the timeline scrubber restores checkpoints (every --every steps), or,
when the model cannot be checkpointed, replays the run from the start.
"""

EPILOG = f"""\
examples:
  modelly studio my_model.py:MyModel
  modelly studio my_model.py:MyModel --port 8800 --no-browser
  modelly studio modelly.examples.advanced.wolf_sheep.model:WolfSheep --seed 7
  modelly studio model.py:Epidemic --portrayal app.py:agent_portrayal

panels:
  run controls   step, run N steps, play and pause, reset
  parameters     one input per Scenario field, and the seed
  timeline       scrub to any recorded step; replay from it with changed values
  space          the grid, network or continuous space, as SpaceRenderer draws it
  reporters      the DataCollector's numeric model reporters
  agents         the first agents, filtered by class
  profiler       modelly profile over the last steps
  lint           modelly lint on the model's file, with --explain text
  log            what happened in the run
  export         figure (PNG, SVG), data (CSV, Parquet), checkpoint, GIF

exit codes:
  0  the server stopped normally (Ctrl+C)
  1  the model raised while being built
  2  bad command line, or the model cannot be found

guide: {GUIDE}
"""


def positive(text: str) -> int:
    """An integer of at least 1."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {text}")
    return value


def port_number(text: str) -> int:
    """A TCP port, or 0 for any free one."""
    value = int(text)
    if not 0 <= value <= MAX_PORT:
        raise argparse.ArgumentTypeError(f"expected a port from 0 to 65535, got {text}")
    return value


OPTIONS = (
    (("target",), {"help": "path/to/model.py:ModelClass or package.module:ModelClass"}),
    (
        ("--port",),
        {
            "type": port_number,
            "default": DEFAULT_PORT,
            "help": "port to serve on; 0 picks a free one (default: %(default)s)",
        },
    ),
    (
        ("--host",),
        {
            "default": LOCALHOST,
            "help": "address to listen on (default: %(default)s, this computer only)",
        },
    ),
    (
        ("--no-browser",),
        {"action": "store_true", "help": "do not open the default browser"},
    ),
    (
        ("--seed",),
        {
            "type": int,
            "default": DEFAULT_SEED,
            "help": "seed of the first run (default: %(default)s)",
        },
    ),
    (
        ("--portrayal",),
        {
            "metavar": "FILE.py:FUNCTION",
            "help": "agent portrayal function; one colour per agent class by default",
        },
    ),
    (
        ("--every",),
        {
            "type": positive,
            "default": DEFAULT_EVERY,
            "help": "steps between two timeline checkpoints (default: %(default)s)",
        },
    ),
    (
        ("--profile-steps",),
        {
            "type": positive,
            "default": DEFAULT_PROFILE_STEPS,
            "metavar": "N",
            "help": "steps the profiler panel sums (default: %(default)s)",
        },
    ),
    (
        ("--memory-budget",),
        {
            "type": positive,
            "default": DEFAULT_BUDGET_MIB,
            "metavar": "MIB",
            "help": "mebibytes the checkpoints may take (default: %(default)s)",
        },
    ),
)


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The parser; ``prog`` names the command in --help."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    for flags, options in OPTIONS:
        parser.add_argument(*flags, **options)
    return parser


def config_from(args: argparse.Namespace) -> StudioConfig:
    """The Studio settings the command line asks for."""
    return StudioConfig(
        target=args.target,
        portrayal=args.portrayal,
        seed=args.seed,
        every=args.every,
        profile_steps=args.profile_steps,
        memory_budget_mib=args.memory_budget,
    )


def free_port(host: str) -> int:
    """A port nothing listens on now, picked by the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return probe.getsockname()[1]


def open_when_ready(server, url: str) -> None:
    """Open ``url`` in the default browser once ``server`` has started."""

    def wait_and_open() -> None:
        while not server.started:
            if server.should_exit:
                return
            time.sleep(BROWSER_POLL_S)
        webbrowser.open(url)

    threading.Thread(target=wait_and_open, daemon=True).start()


def serve(config: StudioConfig, host: str, port: int, browser: bool) -> None:
    """Serve the Studio app until Ctrl+C."""
    # Solara warns that a cookie cannot be samesite=none over plain http on 127.0.0.1;
    # it falls back to samesite=lax, which is right for a local server.
    warnings.filterwarnings("ignore", message=SAMESITE_WARNING, category=UserWarning)
    config.export()
    os.environ["SOLARA_APP"] = APP
    os.environ["SERVER_NAME"], os.environ["SERVER_PORT"] = host, str(port)
    import uvicorn  # noqa: PLC0415 (installed with solara, the viz extra)

    server = uvicorn.Server(
        uvicorn.Config(
            "solara.server.starlette:app", host=host, port=port, log_level="warning"
        )
    )
    url = f"http://{host}:{port}"
    sys.stdout.write(f"Modelly Studio: {url} (Ctrl+C to stop)\n")
    if browser:
        open_when_ready(server, url)
    server.run()


def check_target(config: StudioConfig) -> int | None:
    """Build the model once, so errors show before the server starts; an exit status on error."""
    if importlib.util.find_spec("solara") is None:
        sys.stderr.write(
            "modelly studio needs the viz extra: pip install modelly-abm[viz]\n"
        )
        return EXIT_USAGE
    for name, value in SOLARA_ENVIRONMENT.items():
        os.environ.setdefault(name, value)  # before Solara reads its settings
    from modelly.studio.app import new_session  # noqa: PLC0415 (needs solara)

    try:
        new_session(config)
    except TargetError as error:
        sys.stderr.write(f"modelly studio: {error}\n")
        return EXIT_USAGE
    except Exception as error:  # a model error is reported, not raised
        sys.stderr.write(
            f"modelly studio: building {config.target} raised {type(error).__name__}: {error}\n"
        )
        return EXIT_MODEL_ERROR
    return None


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Serve Studio for the model the command line names; the exit status."""
    args = build_parser(prog).parse_args(argv)
    config = config_from(args)
    failed = check_target(config)
    if failed is not None:
        return failed
    port = args.port or free_port(args.host)
    serve(config, args.host, port, not args.no_browser)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
