"""Suite-wide pytest configuration.

Browser tests (``solara_test``, ``page_session``) start a solara server. The solara
pytest plugin defaults to a fixed port (18865), so two test runs on one machine
collide. Port 0 makes the plugin's server bind a free port chosen by the OS.
An explicit ``--solara-port`` (or ``PORT`` in the environment) still wins.

Property-based tests (Hypothesis) run under the ``modelly`` profile: derandomized, so
every run and every CI platform tries the same examples, few enough examples to stay
fast, a deadline per example, and no example database written into the checkout.
"""

import os
from datetime import timedelta

from hypothesis import settings

HYPOTHESIS_PROFILE = "modelly"
HYPOTHESIS_EXAMPLES = 40
HYPOTHESIS_DEADLINE = timedelta(seconds=2)
settings.register_profile(
    HYPOTHESIS_PROFILE,
    derandomize=True,
    max_examples=HYPOTHESIS_EXAMPLES,
    deadline=HYPOTHESIS_DEADLINE,
    database=None,
    print_blob=True,
)
settings.load_profile(HYPOTHESIS_PROFILE)

FREE_PORT = 0
PORT_OPTIONS = {
    "solara_port": "--solara-port",
    "jupyter_port": "--jupyter-port",
    "voila_port": "--voila-port",
}


def _named_on_command_line(config, flag):
    return any(arg.split("=")[0] == flag for arg in config.invocation_params.args)


def pytest_configure(config):  # noqa: D103
    if "PORT" in os.environ:
        return
    for dest, flag in PORT_OPTIONS.items():
        if hasattr(config.option, dest) and not _named_on_command_line(config, flag):
            setattr(config.option, dest, FREE_PORT)
