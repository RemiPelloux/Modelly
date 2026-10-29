"""Files that let someone else rerun what Studio showed: the session script and a bundle.

``session_script`` is the Python script of the session's live run (see
``modelly.studio.recording``). ``bundle_bytes`` runs the live run again with ``modelly run``'s
recorder and packs it with ``modelly bundle``: a zip with the manifest, the outputs, the model
code, the seeds and the lock file, which ``modelly verify`` checks. A manifest records one run
built from its parameters and stepped on, so a live run that came from Replay from here has a
script but no bundle.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from modelly.provenance.bundle import bundle_entries, zip_bytes
from modelly.provenance.runner import RunSpec, run_study

if TYPE_CHECKING:
    from modelly.studio.session import StudioSession

SCRIPT_ENCODING = "utf-8"
RUN_FOLDER = "run"
NOT_STRAIGHT = (
    "the live run came from Replay from here, which a manifest cannot record: "
    "export the session script instead, or Reset and run again"
)


def script_name(session: StudioSession) -> str:
    """The file name the session script downloads as."""
    shown = session.model
    return f"{type(shown).__name__.lower()}_session_step{shown.time:g}.py"


def session_script(session: StudioSession) -> bytes:
    """The Python script that rebuilds the session's live run, as UTF-8 bytes."""
    model = session.model
    text = session.recording.script(
        model.time, type(model).__name__, script_name(session)
    )
    return text.encode(SCRIPT_ENCODING)


def bundle_spec(session: StudioSession, out: Path) -> RunSpec:
    """The ``modelly run`` of the live run: its values and seed, as many steps as it took.

    Raises:
        ValueError: When the live run came from a replay (see ``NOT_STRAIGHT``).
    """
    recording = session.recording
    if not recording.straight:
        raise ValueError(NOT_STRAIGHT)
    first = recording.segments[0]
    steps = round(session.model.time - first.start)
    return RunSpec(
        target=session.config.target,
        out=out,
        steps=steps,
        seed=first.seed,
        params=dict(first.values),
    )


def bundle_bytes(session: StudioSession) -> bytes:
    """The live run rerun, recorded and packed as a ``modelly bundle`` zip.

    Raises:
        ValueError: When the live run came from a replay.
    """
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / RUN_FOLDER
        run_study(bundle_spec(session, out))
        return zip_bytes(bundle_entries(out))


__all__ = ["bundle_bytes", "bundle_spec", "script_name", "session_script"]
