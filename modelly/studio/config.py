"""What one Studio server shows: the model, its portrayal and the panels' settings.

The command line builds a ``StudioConfig`` and hands it to the Solara app through one
environment variable as JSON, so the app module finds it however Solara imports it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

ENV_VAR = "MODELLY_STUDIO_CONFIG"
DEFAULT_SEED = 42
DEFAULT_EVERY = 1
DEFAULT_PROFILE_STEPS = 50
DEFAULT_TABLE_ROWS = 100
MEBIBYTE = 2**20
DEFAULT_BUDGET_MIB = 256


@dataclass(frozen=True)
class StudioConfig:
    """The settings of a Studio session.

    Attributes:
        target: ``path/to/model.py:ModelClass`` or ``package.module:ModelClass``.
        portrayal: ``path/to/app.py:function`` or ``package.module:function`` returning an
            ``AgentPortrayalStyle`` per agent; one colour per agent class when None.
        seed: The seed the first run starts from.
        every: Steps between two checkpoints of the timeline.
        profile_steps: How many of the last steps the profiler panel sums.
        table_rows: Rows the agent table shows.
        memory_budget_mib: Mebibytes the timeline's checkpoints may take.
    """

    target: str
    portrayal: str | None = None
    seed: int = DEFAULT_SEED
    every: int = DEFAULT_EVERY
    profile_steps: int = DEFAULT_PROFILE_STEPS
    table_rows: int = DEFAULT_TABLE_ROWS
    memory_budget_mib: int = DEFAULT_BUDGET_MIB

    @property
    def memory_budget(self) -> int:
        """The checkpoint budget in bytes."""
        return self.memory_budget_mib * MEBIBYTE

    @property
    def source_file(self) -> Path | None:
        """The model's ``.py`` file when the target names one, for the lint panel."""
        source = self.target.rpartition(":")[0]
        return Path(source) if source.endswith(".py") else None

    def to_json(self) -> str:
        """The config as JSON."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> StudioConfig:
        """A config from ``to_json`` output."""
        return cls(**json.loads(text))

    def export(self) -> None:
        """Put the config in the environment, for the app module to read."""
        os.environ[ENV_VAR] = self.to_json()

    @classmethod
    def from_environment(cls) -> StudioConfig:
        """The config ``export`` put in the environment.

        Raises:
            RuntimeError: When there is none, i.e. the app was not started by
                ``modelly studio``.
        """
        text = os.environ.get(ENV_VAR)
        if not text:
            raise RuntimeError(
                f"{ENV_VAR} is not set: start Studio with `modelly studio path/to/model.py:Model`"
            )
        return cls.from_json(text)
