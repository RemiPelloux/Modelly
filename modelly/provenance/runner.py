"""Run a model once and record it: outputs on disk and a manifest next to them."""

from __future__ import annotations

import inspect
import secrets
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modelly.core.model import Model
from modelly.profile.loader import TargetError, build_model, load_class
from modelly.provenance.code import code_record
from modelly.provenance.environment import environment
from modelly.provenance.files import hash_file, relative_posix
from modelly.provenance.llm import FIELD, cache_record
from modelly.provenance.manifest import FORMAT, json_safe, write_manifest
from modelly.provenance.outputs import collected_tables, write_tables

# Bits of a seed drawn when none is given; the drawn seed is recorded.
SEED_BITS = 32
SEED_KEY = "seed"


@dataclass
class RunSpec:
    """What ``modelly run`` was asked to do."""

    target: str
    out: Path
    steps: int
    seed: int | None = None
    scenario: Path | None = None
    params: dict[str, Any] = field(default_factory=dict)
    inputs: tuple[Path, ...] = ()


@dataclass
class Run:
    """A finished run: the model, its outputs and how long it took."""

    model: Model
    outputs: list[dict]
    wall_seconds: float
    cpu_seconds: float


def read_scenario(path: Path | None) -> dict[str, Any]:
    """The parameters of a TOML scenario file (a flat table); ``{}`` for no file."""
    if path is None:
        return {}
    try:
        return tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise TargetError(f"cannot read scenario {path}: {error}") from error


def execute(cls: type[Model], params: dict, seed: int, steps: int) -> Model:
    """Build ``cls`` with ``params`` and ``seed`` and run it for ``steps`` steps."""
    model = build_model(cls, params, seed)
    model.run_for(steps)
    return model


def timed_run(cls: type[Model], params: dict, seed: int, steps: int) -> Run:
    """Run the model, collecting wall-clock and CPU time; outputs are not written yet."""
    wall, cpu = time.perf_counter(), time.process_time()
    model = execute(cls, params, seed, steps)
    return Run(model, [], time.perf_counter() - wall, time.process_time() - cpu)


def target_record(spec_target: str, cls: type[Model]) -> tuple[dict, Path]:
    """The manifest's target block and the code root (the class's folder)."""
    source = spec_target.rpartition(":")[0]
    root = Path(inspect.getfile(cls)).resolve().parent
    if source.endswith(".py"):
        return {
            "class": cls.__name__,
            "kind": "file",
            "source": Path(source).name,
        }, root
    return {"class": cls.__name__, "kind": "module", "source": source}, root


def seeds_record(model: Model, seed: int) -> dict:
    """The seed and the seed sequence it expanded to, as the model's scenario holds them."""
    sequence = model.scenario.seed_sequence
    return {
        "entropy": json_safe(sequence.entropy),
        "seed": seed,
        "spawn_key": list(sequence.spawn_key),
        "stdlib_seed": model.scenario._stdlib_seed,
    }


def scenario_record(spec: RunSpec, params: dict, model: Model, out: Path) -> dict:
    """The scenario file, its hash, the parameters given and the values the model used."""
    record = {"file": None, "hash": None, "parameters": params}
    if spec.scenario is not None:
        record["file"] = relative_posix(spec.scenario, out)
        record["hash"] = hash_file(spec.scenario)
    record["resolved"] = {k: json_safe(v) for k, v in dict(model.scenario).items()}
    return record


def resolve_parameters(spec: RunSpec) -> tuple[dict, int]:
    """The run's parameters (scenario file, then --param) and its seed."""
    params = {**read_scenario(spec.scenario), **spec.params}
    file_seed = params.pop(SEED_KEY, None)
    seed = spec.seed if spec.seed is not None else file_seed
    if seed is None:
        seed = secrets.randbits(SEED_BITS)
    return params, int(seed)


def manifest_record(spec: RunSpec, cls: type[Model], run: Run, setup: tuple) -> dict:
    """Assemble the manifest of a finished run; ``setup`` is ``(params, seed)``."""
    params, seed = setup
    out = Path(spec.out)
    target, root = target_record(spec.target, cls)
    inputs = [
        {"hash": hash_file(path), "path": relative_posix(path, out)}
        for path in sorted(Path(p) for p in spec.inputs)
    ]
    return {
        "code": code_record(root, relative_posix(root, out)),
        "environment": environment(),
        "format": FORMAT,
        "inputs": inputs,
        "outputs": run.outputs,
        "run": {"seed": seed, "steps": spec.steps},
        "scenario": scenario_record(spec, params, run.model, out),
        "seeds": seeds_record(run.model, seed),
        "target": target,
        "timing": {"cpu_seconds": run.cpu_seconds, "wall_seconds": run.wall_seconds},
    }


def run_study(spec: RunSpec) -> dict:
    """Run the model ``spec`` names, write its outputs and manifest to ``spec.out``.

    Raises TargetError when the target, scenario or inputs cannot be used; anything
    the model raises propagates.
    """
    missing = [str(path) for path in spec.inputs if not Path(path).is_file()]
    if missing:
        raise TargetError(f"no such input file(s): {', '.join(missing)}")
    setup = resolve_parameters(spec)
    cls = load_class(spec.target)
    run = timed_run(cls, *setup, spec.steps)
    run.outputs = write_tables(collected_tables(run.model), Path(spec.out))
    record = manifest_record(spec, cls, run, setup)
    replies = cache_record(run.model, Path(spec.out))
    if replies is not None:
        record[FIELD] = replies
    write_manifest(spec.out, record)
    return record
