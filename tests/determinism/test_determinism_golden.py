"""Every bundled example reproduces its golden digest, on every platform and build.

When a deliberate change alters an example's results, regenerate the file with
``python -m modelly.dev golden --update`` and commit it with the change.
"""

import json
from pathlib import Path

import pytest

import modelly.examples
from modelly.dev.golden import (
    EXAMPLES,
    EXAMPLES_BY_NAME,
    GOLDEN,
    JSON_INDENT,
    PLATFORM,
    SEED,
    golden_digest,
    golden_record,
    read_golden,
    recorded_platform,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / GOLDEN
EXAMPLES_DIR = Path(modelly.examples.__file__).parent
OTHER_SEED = SEED + 1


def test_every_example_folder_is_in_the_suite():
    """A new example folder must be added to modelly.dev.golden.EXAMPLES."""
    folders = {path.parent.name for path in EXAMPLES_DIR.glob("*/*/model.py")}
    assert folders == set(EXAMPLES_BY_NAME)


def test_golden_file_records_every_example_as_written():
    """The file names every example, with its steps and float digits, in LF form."""
    data = GOLDEN_PATH.read_bytes()
    assert b"\r" not in data
    recorded = read_golden(GOLDEN_PATH)
    assert set(recorded) == set(EXAMPLES_BY_NAME)
    record = golden_record(recorded, recorded_platform(GOLDEN_PATH))
    expected = json.dumps(record, indent=JSON_INDENT, sort_keys=True)
    assert data.decode("utf-8") == expected + "\n"


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.name)
def test_golden_digest(example):
    """The example, run from the golden seed, gives the recorded digest."""
    if not example.available():
        pytest.skip(f"{example.name} needs {', '.join(example.requires)}")
    if example.machine_only and recorded_platform(GOLDEN_PATH) != PLATFORM:
        pytest.skip(f"{example.name}: {example.machine_only}")
    assert golden_digest(example) == read_golden(GOLDEN_PATH)[example.name]


def test_another_seed_gives_another_digest():
    """The digest depends on the run: a different seed changes it."""
    example = EXAMPLES_BY_NAME["boltzmann_wealth_model"]
    assert golden_digest(example, OTHER_SEED) != golden_digest(example)
