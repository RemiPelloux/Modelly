"""The reproducible exports: the session script and the ``modelly bundle`` of the live run."""

import io
import json
import zipfile

import pytest

from modelly.provenance.verify import verify
from modelly.studio import exports
from tests.studio.test_studio_recording import (
    WOLF_SHEEP,
    replayed,
    session_of,
    state_of,
)

pytest.importorskip("pyarrow")

BOLTZMANN = "modelly/examples/basic/boltzmann_wealth_model/model.py:BoltzmannWealth"


def test_the_bundle_records_the_live_run(tmp_path):
    """The zip holds the manifest of the run's values, seed and steps, and verifies."""
    session = session_of(BOLTZMANN)
    session.values["n"] = 30
    session.seed = 4
    session.reset()
    session.step(6)
    archive = zipfile.ZipFile(io.BytesIO(exports.bundle_bytes(session)))
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["run"] == {"seed": 4, "steps": 6}
    assert manifest["scenario"]["parameters"]["n"] == 30
    assert {"code/model.py", "requirements.lock", "seeds.json"} <= set(
        archive.namelist()
    )
    archive.extractall(tmp_path)
    assert verify(tmp_path / "manifest.json").matches


def test_a_replayed_run_has_a_script_but_no_bundle():
    """After Replay from here the bundle refuses, and the script still rebuilds the run."""
    session = session_of(WOLF_SHEEP)
    session.step(4)
    session.scrub(2)
    session.replay()
    with pytest.raises(ValueError, match="Replay from here"):
        exports.bundle_bytes(session)
    script = exports.session_script(session).decode("utf-8")
    assert state_of(replayed(script)) == state_of(session.model)
    assert exports.script_name(session) == "wolfsheep_session_step2.py"
