"""The coupling schedule: build-time consistency checks, ordering and checkpoints."""

import pickle

import numpy as np
import pytest

from modelly.core.model import Model
from modelly.couple.field import Field, Transport
from modelly.couple.ode import ODE
from modelly.couple.schedule import Coupling, CouplingError, Phase
from modelly.space.grid.grids import OrthogonalMooreGrid


class Recorder:
    """A callable that logs its name when run, standing in for an agent phase."""

    def __init__(self, name, log):
        """Log into ``log`` under ``name``."""
        self.__name__ = name
        self.log = log

    def __call__(self):
        """Record the call."""
        self.log.append(self.__name__)


def phase(name, log, reads=(), writes=(), initial=None):
    """A ``Phase`` around a ``Recorder``."""
    return Phase(Recorder(name, log), reads, writes, initial)


def test_read_with_no_writer_is_refused_with_a_suggestion():
    """A typo in a read is caught at build, with the close quantity named."""
    coupling = Coupling()
    coupling.add(phase("a", [], writes=("nutrient",)))
    coupling.add(phase("b", [], reads=("nutrients",)))
    with pytest.raises(CouplingError, match=r"nobody writes.*'nutrient'"):
        coupling.build()


def test_two_writers_are_refused():
    """One quantity, one writer."""
    coupling = Coupling()
    coupling.add(phase("a", [], writes=("x",)))
    coupling.add(phase("b", [], writes=("x",)), phase=3)
    with pytest.raises(CouplingError, match=r"two writers.*'a'.*'b'"):
        coupling.build()


def test_a_cycle_inside_a_phase_is_refused():
    """``a`` reads ``b``'s output and ``b`` reads ``a``'s, both in phase 0."""
    coupling = Coupling()
    coupling.add(phase("a", [], reads=("y",), writes=("x",)))
    coupling.add(phase("b", [], reads=("x",), writes=("y",)))
    with pytest.raises(CouplingError, match=r"cycle.*later phase"):
        coupling.build()


def test_the_same_loop_across_two_phases_is_a_lagged_feedback():
    """Split over phases the loop is fine; the earlier reader sees last step's value."""
    log = []
    coupling = Coupling()
    coupling.add(phase("a", log, reads=("y",), writes=("x",)))
    coupling.add(
        phase("b", log, reads=("x",), writes=("y",), initial={"y": 0}), phase=1
    )
    coupling.build()
    coupling.step()
    coupling.step(0.5)
    assert log == ["a", "b", "a", "b"]
    assert coupling.time == 1.5


def test_a_lagged_read_needs_an_initial_value():
    """Reading a quantity before its writer has ever run needs a starting value."""
    coupling = Coupling()
    coupling.add(phase("a", [], reads=("y",)))
    coupling.add(phase("b", [], writes=("y",)), phase=1)
    with pytest.raises(CouplingError, match="no initial value"):
        coupling.build()


def test_writers_run_before_readers_inside_a_phase():
    """Insertion order is kept unless a reader was added before its writer."""
    log = []
    coupling = Coupling()
    coupling.add(phase("reader", log, reads=("x",)))
    coupling.add(phase("other", log))
    coupling.add(phase("writer", log, writes=("x",)))
    coupling.add(phase("late", log), phase=-1)
    assert coupling.build().order == [
        "Phase 'late'",
        "Phase 'other'",
        "Phase 'writer'",
        "Phase 'reader'",
    ]
    coupling.step()
    assert log == ["late", "other", "writer", "reader"]


def test_undeclared_writes_are_refused_during_a_step():
    """A component may only set the quantities it declares."""

    class Sneaky:
        """Writes a quantity it did not declare."""

        label, reads, writes = "Sneaky", (), ("x",)

        def start(self, coupling):
            """Nothing to publish."""

        def run(self, coupling, time, duration):
            """Write ``y`` instead of ``x``."""
            coupling["y"] = 1.0

    coupling = Coupling()
    coupling.add(Sneaky())
    with pytest.raises(CouplingError, match="does not declare"):
        coupling.step()  # step builds the schedule first
    coupling["y"] = 2.0  # outside a step, set-up code may write anything
    assert coupling["y"] == 2.0


def test_initial_values_must_be_writes():
    """A phase cannot seed a quantity it does not write."""
    with pytest.raises(CouplingError, match="does not write"):
        phase("a", [], writes=("x",), initial={"y": 0})


def test_adding_after_build_rebuilds():
    """A component added later joins the order at the next step."""
    log = []
    coupling = Coupling()
    coupling.add(phase("a", log))
    coupling.build()
    coupling.add(phase("b", log))
    coupling.step()
    assert log == ["a", "b"]


def relax(t, y, inputs):
    """``y' = mean(field) - y``: the ODE follows the field's mean."""
    return np.mean(inputs["heat"]) - y


class Coupled(Model):
    """A model with an implicit field, an ODE reading it and an agent phase feeding it."""

    def __init__(self, rng=1):
        """A 9 x 9 grid, a heat field with a random source, an ODE following its mean."""
        super().__init__(rng=rng)
        self.grid = OrthogonalMooreGrid((9, 9), random=self.random)
        transport = Transport(diffusion=2.0, decay=0.1, scheme="implicit", dt=0.5)
        self.coupling = Coupling()
        self.coupling.add(Phase(self.heat_up, writes=("source",)))
        self.field = self.coupling.add(
            Field(self.grid, "heat", transport, source="source"), 1
        )
        self.coupling.add(ODE(relax, {"mean": 0.0}, reads=("heat",)), phase=2)
        self.coupling.build()

    def heat_up(self):
        """Drop random heat on the grid."""
        self.coupling["source"] = self.rng.random((9, 9))

    def step(self):
        """One coupled step."""
        self.coupling.step()


def test_checkpoint_round_trips_bit_for_bit(tmp_path):
    """Run 10, save, load and run 10 more: the same field, ODE and budget as 20 straight."""
    straight = Coupled()
    straight.run_for(20)
    resumed = Coupled()
    resumed.run_for(10)
    resumed.save(tmp_path / "coupled.ckpt")
    loaded = Coupled.load(tmp_path / "coupled.ckpt")
    assert loaded.field.values is loaded.grid.property_layers["heat"]
    assert loaded.coupling["heat"] is loaded.field.values
    loaded.run_for(10)
    assert np.array_equal(loaded.field.values, straight.field.values)
    assert loaded.coupling.values["mean"] == straight.coupling.values["mean"]
    assert (loaded.field.added, loaded.field.decayed) == (
        straight.field.added,
        straight.field.decayed,
    )
    assert loaded.grid._cells[(4, 4)].heat == straight.field.values[4, 4]


def test_pickle_drops_the_factorisation():
    """The cached LU solve does not pickle; it is rebuilt on the next step."""
    model = Coupled()
    model.step()
    assert model.field._solvers
    copy = pickle.loads(pickle.dumps(model.field))  # noqa: S301 - our own bytes
    assert copy._solvers == {}
    assert np.array_equal(copy.values, model.field.values)


def test_a_field_with_a_source_balances_its_budget():
    """``total = added - decayed`` when the field starts empty with closed walls."""
    model = Coupled(rng=5)
    model.run_for(15)
    field = model.field
    assert field.total() == pytest.approx(field.added - field.decayed, rel=1e-12)


def test_a_rebuild_keeps_the_current_values():
    """Initial values seed a quantity once; rebuilding does not reset it."""
    coupling = Coupling()
    coupling.add(phase("a", [], writes=("x",), initial={"x": 0}))
    coupling.build()
    coupling["x"] = 5
    coupling.add(phase("b", [], reads=("x",)))
    coupling.build()
    assert coupling["x"] == 5
