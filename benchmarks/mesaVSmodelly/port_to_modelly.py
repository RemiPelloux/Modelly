"""Generate the Modelly port of the optimized Mesa 2.3 notebook.

Reads ``mesa/Notebook_ABM_TIS_Optimise.ipynb`` and writes
``modelly/Notebook_ABM_TIS_Optimise_Modelly.ipynb`` with the *minimum* set of
API changes needed to run the identical simulation on Modelly (a Mesa 4.x
fork). Everything else — parameters, experiments, seeds, plots — is untouched.

Porting rules
-------------
1. ``import mesa`` -> ``import modelly`` (+ ``import random``).
2. ``mesa.Agent``/``mesa.Model``/``mesa.DataCollector`` -> ``modelly.*``.
3. ``super().__init__(model.next_id(), model)`` -> ``super().__init__(model)``
   (Modelly assigns ``unique_id`` itself in ``register_agent``).
4. ``Fruit_Agent`` stays a plain object (FIX 6); its id comes from a new
   ``model.next_fruit_id()`` instead of Mesa's ``model.next_id()``.
5. Mesa 2.3's ``model.agents_[Type]`` dict becomes Modelly's ``model.agents``
   ``_HardKeyAgentSet`` (O(1) ``in`` via a dict, same semantics).
6. ``RematingModel`` is seeded with ``super().__init__(rng=seed)`` and then
   ``self.random = random.Random(seed)`` — the *exact* same ``random.Random``
   stream Mesa 2.3 builds in ``Model.__new__`` — so both notebooks produce
   bit-identical CSVs.
7. Modelly auto-advances ``model.time`` through an event schedule, which would
   shift the notebook's integer ``self.time`` semantics by one. The model's
   ``step()`` is therefore renamed ``advance_day()`` and drives its own
   ``self.time`` counter; every ``model.step()`` call follows. Modelly's
   auto-step is never invoked.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "mesa" / "Notebook_ABM_TIS_Optimise.ipynb"
DST = HERE / "modelly" / "Notebook_ABM_TIS_Optimise_Modelly.ipynb"

# (old, new) applied in order. Anchors are exact substrings of the source.
REPLACEMENTS: list[tuple[str, str]] = [
    # -- framework import + version banner -------------------------------
    ("import mesa\n", "import modelly\nimport random\n"),
    ('"Mesa version :"', '"Modelly version :"'),
    ("mesa", "modelly"),  # catches mesa.Agent / mesa.Model / mesa.DataCollector
    # -- agent construction (Mesa 2.x -> Mesa 4 / Modelly) ----------------
    ("super().__init__(model.next_id(), model)", "super().__init__(model)"),
    # -- Fruit_Agent is a plain object; give it a model-side id -----------
    ("self.unique_id = model.next_id()", "self.unique_id = model.next_fruit_id()"),
    # -- liveness checks: Mesa dict -> Modelly AgentSet -------------------
    ("if self in self.model.agents_[Larvae_Agent]:", "if self in self.model.agents:"),
    ("alive = self.model.agents_[Larvae_Agent]", "alive = self.model.agents"),
    # -- RematingModel.__init__: native seeding + fruit-id counter --------
    (
        "        super().__init__()\n"
        "        self.time, self.crop, self.sperm_selection = 0, crop_parameters, sperm_selection\n",
        "        super().__init__(rng=seed)\n"
        "        # Same random.Random(seed) stream as Mesa 2.3's Model.__new__\n"
        "        # -> bit-identical trajectories for the same seed.\n"
        "        self.random = random.Random(seed)\n"
        "        self._fruit_id_counter = 0\n"
        "        self.time, self.crop, self.sperm_selection = 0, crop_parameters, sperm_selection\n",
    ),
    # -- add the fruit-id helper between __init__ and create_fruit --------
    (
        "        self.collect_data()\n\n    def create_fruit(self):\n",
        "        self.collect_data()\n"
        "\n"
        "    def next_fruit_id(self):\n"
        '        """Return the next fruit id (fruits are plain objects, not Modelly agents)."""\n'
        "        uid = self._fruit_id_counter\n"
        "        self._fruit_id_counter += 1\n"
        "        return uid\n"
        "\n"
        "    def create_fruit(self):\n",
    ),
    # -- step(): iterate agents grouped by type, exactly like Mesa 2.3 ---------
    (
        "        agents_ = self.agents_\n"
        "        agents = [a for bucket in agents_.values() for a in bucket]\n",
        "        # Mesa 2.3 iterates agents_ grouped by type; Modelly's agents_by_type\n"
        "        # keeps that same order, so the shuffle consumes the same RNG stream.\n"
        "        agents = [a for bucket in self.agents_by_type.values() for a in bucket]\n",
    ),
    (
        "            if a in agents_[type(a)]: a.step()\n",
        "            if a in self.agents: a.step()\n",
    ),
    # -- rename the model step so it doesn't collide with Modelly's auto-step
    (
        "    def step(self):\n        if self.crop.daily_fruit_production > 0:\n",
        "    def advance_day(self):\n"
        "        if self.crop.daily_fruit_production > 0:\n",
    ),
    ("model.step()", "model.advance_day()"),
]


def transform_cell(source: str) -> str:
    """Apply all replacements to one cell's source (anchors may be absent)."""
    for old, new in REPLACEMENTS:
        source = source.replace(old, new)
    return source


def main() -> None:
    nb = json.loads(SRC.read_text(encoding="utf-8"))

    hits: dict[str, int] = {old: 0 for old, _ in REPLACEMENTS}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        for old, _ in REPLACEMENTS:
            hits[old] += source.count(old)
        source = transform_cell(source)
        cell["source"] = source.splitlines(keepends=True)

    # Every anchor must have been found at least once across the notebook,
    # otherwise the source changed under us and the port is silently partial.
    missing = [old for old, n in hits.items() if n == 0]
    if missing:
        raise SystemExit(f"anchors never matched: {missing}")

    # Tag the notebook so it is self-describing.
    banner = (
        "# ============================================================\n"
        "# PORT MODELLY du notebook optimisé (voir benchmarks/mesaVSmodelly/README.md)\n"
        "# Mêmes paramètres, mêmes expériences, mêmes seeds que la version Mesa.\n"
        "# ============================================================\n"
    )
    first = nb["cells"][0]
    first["source"] = [banner] + list(first["source"])

    DST.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {DST}")


if __name__ == "__main__":
    main()
