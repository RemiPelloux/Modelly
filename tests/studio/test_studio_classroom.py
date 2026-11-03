"""Classroom mode: shared parameters, submitted runs, the class's table."""

import pytest

solara = pytest.importorskip("solara")

from modelly.studio import app, classroom  # noqa: E402
from modelly.studio.config import StudioConfig  # noqa: E402

BOLTZMANN = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"


def test_shared_parameters_reach_new_sessions_and_runs_are_collected(tmp_path):
    """The instructor shares n = 30; two students run and submit; the table has both."""
    teacher = app.new_session(StudioConfig(target=BOLTZMANN, classroom=str(tmp_path)))
    teacher.values["n"] = 30
    classroom.share(teacher, tmp_path)
    for name, seed in (("Ana", 1), ("Bo Li", 2)):
        student = app.new_session(
            StudioConfig(target=BOLTZMANN, classroom=str(tmp_path), seed=seed)
        )
        assert student.values["n"] == 30
        student.step(5)
        classroom.submit(student, tmp_path, name)
    runs = classroom.submissions(tmp_path)
    assert list(runs["student"]) == ["Ana", "Bo Li"] and set(runs["n"]) == {30}
    assert "Gini" in runs.columns and (runs["steps"] == 5).all()
    with pytest.raises(ValueError, match="name"):
        classroom.submit(student, tmp_path, "  ")
    assert not list(tmp_path.glob("runs/.*.tmp"))
