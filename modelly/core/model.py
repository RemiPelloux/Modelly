"""The model class for Modelly framework.

Core Objects: Model
"""

# Postpone annotation evaluation to avoid NameError from forward references (PEP 563). Remove once Python 3.14+ is required.
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Self

import numpy as np

from modelly.core.agent import Agent
from modelly.core.checkpoint import CheckpointWriter, load_model, save_model
from modelly.core.columns import ColumnStore
from modelly.core.exceptions import CheckpointError
from modelly.core.registry import AgentRegistry
from modelly.core.rng import FastRandom
from modelly.data.recorders.datasets import DataRegistry
from modelly.log import create_module_logger, method_logger
from modelly.scenarios import Scenario
from modelly.time import (
    EventGenerator,
    EventList,
    Priority,
    Schedule,
)
from modelly.time.schedule import HasSchedule
from modelly.time.signals import (
    HasEmitters,
    ModelSignals,
    ObservableSignals,
)

SeedLike = int | np.integer | Sequence[int] | np.random.SeedSequence
RNGLike = np.random.Generator | np.random.BitGenerator


_modelly_logger = create_module_logger()

# Subscriber keys and the observable signals of ``agents``; see register_agent.
_AGENT_SIGNALS = frozenset({ModelSignals.AGENT_ADDED, ModelSignals.AGENT_REMOVED})


# TODO: We can add `= Scenario` default type when Python 3.13+ is required
class Model[A: Agent, S: Scenario](AgentRegistry[A], HasSchedule, HasEmitters):
    """Base class for models in the Modelly ABM library.

    This class serves as a foundational structure for creating agent-based models.
    It includes the basic attributes and methods necessary for initializing and
    running a simulation model.

    Type Parameters:
        A: The agent type used in this model
        S: The scenario type used in this model

    Attributes:
        running: A boolean indicating if the model should continue running.
        time: the current simulation time.
        random: a seeded python.random number generator.
        rng: a seeded numpy.random.Generator
        scenario: the scenario instance containing model parameters

    Notes:
        Model.agents returns the AgentSet containing all agents registered with the model. Changing
        the content of the AgentSet directly can result in strange behavior. If you want change the
        composition of this AgentSet, ensure you operate on a copy.

    """

    # time is a plain attribute for speed: reads are ~40ns vs ~100ns through a
    # data descriptor. The CHANGED signal is emitted once per time advance by
    # _set_time(), so BaseDataRecorder and observe("time", ...) keep working.
    # "time" is registered as an observable in __init_subclass__ (below) and at
    # module level for the base Model class itself.

    # True when the class keeps the default registration methods, which lets
    # Agent.__init__ and Agent.remove inline them (see agent.py).
    _default_registry: bool = True

    def __init_subclass__(cls, **kwargs):
        """Register ``time`` as an observable for every Model subclass."""
        super().__init_subclass__(**kwargs)
        cls.observables["time"] = ObservableSignals
        cls.observables["agents"] = _AGENT_SIGNALS
        cls._default_registry = (
            cls.register_agent is Model.register_agent
            and cls.deregister_agent is Model.deregister_agent
        )
        if not cls._default_registry:
            cls._quiet = False  # Agent.__init__ must call the override

    def _init_scenario(
        self, rng: RNGLike | SeedLike | None, scenario: S | type[S]
    ) -> None:
        """Set the scenario and the two generators it seeds."""
        if isinstance(scenario, Scenario) and rng is not None:
            raise ValueError("Pass either rng or scenario, not both.")
        if not isinstance(scenario, Scenario):
            scenario = scenario(rng=rng)  # type: ignore[assignment]

        self.scenario = scenario
        self.rng: np.random.Generator = scenario.rng
        self.random = FastRandom(scenario._stdlib_seed)

    def _init_default_schedule(self) -> None:
        """Wrap the user's step in the default schedule (every 1.0 time units)."""
        self._user_step = self.step
        self._default_schedule: EventGenerator = EventGenerator(
            self,
            self._user_step,
            Schedule(interval=1.0, start=1.0),
            priority=Priority.HIGH,
        ).start()
        self.step = self._wrapped_step

    @property
    def scenario(self) -> S:
        """Return scenario instance."""
        return self._scenario

    @scenario.setter
    def scenario(self, scenario: S) -> None:
        """Set scenario instance."""
        self._scenario = scenario

    @method_logger(__name__)
    def __init__(
        self,
        *args: Any,
        rng: RNGLike | SeedLike | None = None,
        scenario: S | type[S] = Scenario,
        **kwargs: Any,
    ) -> None:
        """Create a new model.

        Overload this method with the actual code to initialize the model. Always start with super().__init__()
        to initialize the model object properly.

        Args:
            args: arguments to pass onto super
            rng: Seed for the random number generator. Accepts any value accepted by
                numpy.random.default_rng(). Ignored if a Scenario instance is passed;
                used to instantiate the scenario when a Scenario class is passed.
            scenario: A Scenario instance or subclass to use for this model. If a class
                is passed it is instantiated with rng. If an instance is passed, rng
                must not be set.
            kwargs: keyword arguments to pass onto super

        Notes:
            Pass either rng or a Scenario instance, not both. Passing rng alongside
            a Scenario class is valid — rng is forwarded to the class constructor.

        """
        super().__init__(*args, **kwargs)
        self.running: bool = True
        self.time = 0.0
        self.agent_id_counter: int = 1

        # Event list for event-based execution
        self._event_list: EventList = EventList()
        # Strong references to active EventGenerators (prevent GC)
        self._event_generators: set[EventGenerator] = set()

        self._init_scenario(rng, scenario)
        self._init_default_schedule()
        self._init_registries()

        self.data_registry = DataRegistry()
        # Column tables for agent classes that declare Column attributes.
        self.columns = ColumnStore(self.random, self.rng)

    def run_model(self) -> None:
        """Run the model until the end condition is reached.

        Overload as needed.
        """
        while self.running:
            self.step()

    def step(self) -> None:
        """A single step. Fill in here."""

    def save(self, path: str | Path, *, compress: bool = False) -> None:
        """Save the whole model to one checkpoint file.

        The file holds the agents, spaces, columns, scheduled events, data
        collected so far and the exact state of ``random`` and ``rng``, so
        ``Model.load`` resumes the run draw for draw.

        Args:
            path: The file to write.
            compress: Gzip the payload (smaller, slower).

        Raises:
            CheckpointError: If a callback the model holds, such as an event
                callback or a reporter, is a lambda or nested function.
        """
        save_model(self, path, compress=compress)

    @classmethod
    def load(cls, path: str | Path) -> Self:
        """Load a model saved with ``save``.

        Warning:
            A checkpoint is a pickle: loading one runs code chosen by whoever
            wrote it. Only load files you created or otherwise trust.

        Args:
            path: The checkpoint file.

        Returns:
            The saved model, an instance of the class it was saved from.

        Raises:
            CheckpointError: If the file is not a checkpoint, was written by
                another Modelly or Python release, or holds no ``cls``.
        """
        model = load_model(path)
        if not isinstance(model, cls):
            raise CheckpointError(
                f"{path} holds a {type(model).__name__}, not a {cls.__name__}."
            )
        return model

    def checkpoint_every(
        self, interval: float, path_pattern: str, *, compress: bool = False
    ) -> CheckpointWriter:
        """Save a checkpoint every ``interval`` time units.

        Args:
            interval: Time between checkpoints; the first is ``interval`` from now.
            path_pattern: The file name, formatted with ``time``, e.g.
                ``"run-{time:04.0f}.ckpt"``.
            compress: Gzip each checkpoint.

        Returns:
            The writer; call its ``stop()`` to end the checkpoints.
        """
        return CheckpointWriter(self, interval, path_pattern, compress)

    def remove_all_agents(self):
        """Remove all agents from the model.

        Notes:
            This method calls agent.remove for all agents in the model. If you need to remove agents from
            e.g., a SingleGrid, you can either explicitly implement your own agent.remove method or clean this up
            near where you are calling this method.

        """
        # we need to wrap keys in a list to avoid a RunTimeError: dictionary changed size during iteration
        for agent in list(self._all_agents):
            agent.remove()

        self.data_registry.close()  # this is needed to ensure GC works properly


# Register "time" as an observable for the base Model class itself (subclasses
# get it via Model.__init_subclass__). Model.time is a plain attribute now, so
# the descriptor generator no longer discovers it automatically.
Model.observables["time"] = ObservableSignals
Model.observables["agents"] = _AGENT_SIGNALS
