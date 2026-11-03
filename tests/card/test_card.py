"""Model cards: the file format, completeness, staleness, stamping and the command line."""

from dataclasses import replace
from pathlib import Path

import pytest

from modelly.card import (
    CardError,
    Check,
    ModelCard,
    card_markdown,
    card_skeleton,
    card_toml,
    problems,
    read_card,
    source_digest,
    stamp,
    write_card,
)
from modelly.card.__main__ import main
from modelly.zoo.age_seir.model import AgeSEIR

MODEL = '"""A tiny model."""\n\nfrom modelly import Model\n\n\nclass Tiny(Model):\n    """Tiny."""\n'
PASSING = "def test_ok():\n    assert True\n"
FAILING = "def test_bad():\n    assert False\n"


def complete(model="model.py:Tiny", test="tests/test_tiny.py") -> ModelCard:
    """A card with every section filled."""
    return ModelCard(
        name="tiny", title="Tiny", model=model, summary="A tiny model.",
        intended_use=("teaching",), out_of_scope=("forecasting",), data=("none",),
        limits=("tiny",), ethics=("none foreseen",), validation=(Check("it runs", test),),
    )  # fmt: skip


@pytest.fixture
def project(tmp_path):
    """A folder with a model file and a passing test."""
    (tmp_path / "model.py").write_text(MODEL)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_tiny.py").write_text(PASSING)
    return tmp_path


def test_a_card_survives_writing_and_reading(tmp_path):
    """``read_card(write_card(card))`` is the card, and the text is the same twice."""
    card = replace(complete(), references=('Quote "this" | that',), sources=("*.py",))
    write_card(card, tmp_path / "card.toml")
    assert read_card(tmp_path / "card.toml") == card
    assert card_toml(read_card(tmp_path / "card.toml")) == card_toml(card)


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("schema = 2\n", "schema"),
        ("schema = 1\n", "name"),
        ("schema = [\n", "card.toml"),
    ],
)
def test_bad_card_files_are_refused(tmp_path, text, match):
    """Another schema, a missing key, broken TOML."""
    (tmp_path / "card.toml").write_text(text)
    with pytest.raises(CardError, match=match):
        read_card(tmp_path / "card.toml")


def test_a_skeleton_is_flagged_until_it_is_filled():
    """Every section starts as a TODO, and the skeleton was never validated."""
    card = card_skeleton(AgeSEIR, "age_seir")
    assert card.model == "modelly.zoo.age_seir.model:AgeSEIR"
    found = problems(card, Path())
    assert "intended_use still has a TODO" in found
    assert "never validated: run `modelly card stamp`" in found


def test_stamping_runs_the_tests_and_records_the_source(project):
    """A passing validation stamps the card; it is fresh until the model changes."""
    path = project / "card.toml"
    write_card(complete(), path)
    passed, _ = stamp(path, project)
    assert passed
    card = read_card(path)
    assert card.validated.source == source_digest(card, project)
    assert problems(card, project) == []
    (project / "model.py").write_text(MODEL + "\nSTEPS = 3\n")
    assert problems(card, project)[0].startswith("stale:")


def test_a_failing_validation_does_not_stamp(project):
    """The card stays unvalidated and the output says why."""
    (project / "tests" / "test_tiny.py").write_text(FAILING)
    path = project / "card.toml"
    write_card(complete(), path)
    passed, output = stamp(path, project)
    assert not passed
    assert "test_bad" in output
    assert read_card(path).validated is None


def test_the_digest_ignores_line_endings_and_follows_the_sources(project):
    """A Windows checkout (CRLF) has the digest of a Linux one; ``sources`` widens it."""
    card = complete()
    lf = source_digest(card, project)
    (project / "model.py").write_bytes(MODEL.replace("\n", "\r\n").encode())
    assert source_digest(card, project) == lf
    wide = replace(card, sources=("*.py", "tests/*.py"))
    assert source_digest(wide, project) != lf
    assert problems(replace(card, model="gone.py:Tiny"), project)[-1].startswith(
        "no source"
    )


def test_markdown_has_every_section():
    """The rendering shows each heading and the validation table."""
    text = card_markdown(complete())
    for heading in ("Intended use", "Out-of-scope use", "Data", "Validation", "Known limits",
                    "Ethical considerations"):  # fmt: skip
        assert f"### {heading}" in text
    assert "| it runs | `tests/test_tiny.py` |" in text
    assert "**Validated:** not yet" in text


def test_the_command_line(project, capsys, monkeypatch):
    """``new`` refuses to overwrite, ``check`` fails until stamped, ``show`` takes zoo names."""
    monkeypatch.chdir(project)
    write_card(complete(), project / "card.toml")
    assert main(["new", "model.py:Tiny"]) == 2
    assert main(["check"]) == 1
    assert main(["stamp", "card.toml"]) == 0
    assert main(["check", "card.toml"]) == 0
    assert main(["new", "model.py:Tiny", "-o", "new.toml"]) == 0
    assert read_card(project / "new.toml").model == "model.py:Tiny"
    capsys.readouterr()
    assert main(["show", "age_seir"]) == 0
    assert "Model card: Age-structured SEIR" in capsys.readouterr().out
    assert main(["show", "no_such_model"]) == 2
