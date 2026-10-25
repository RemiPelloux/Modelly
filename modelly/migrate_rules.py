"""The rewrite tables of ``modelly.migrate``: module map, line rewrites, flags."""

from __future__ import annotations

import re

# Mesa module -> Modelly module. Order matters: longer prefixes first.
MODULE_MAP = (
    ("mesa.experimental.cell_space", "modelly.space"),
    ("mesa.experimental.continuous_space", "modelly.space.continuous"),
    ("mesa.experimental.meta_agents", "modelly.behaviour.meta_agents"),
    ("mesa.experimental.signals", "modelly.time.signals"),
    ("mesa.experimental.scenarios", "modelly.scenarios"),
    ("mesa.experimental.data_collection", "modelly.data.recorders"),
    ("mesa.datacollection", "modelly.data.collector"),
    ("mesa.discrete_space", "modelly.space"),
    ("mesa.visualization", "modelly.viz"),
    ("mesa.batchrunner", "modelly.scenarios"),
    ("mesa.space", "modelly.space"),
    ("mesa.agent", "modelly.core.agent"),
    ("mesa.model", "modelly.core.model"),
    ("mesa.time", "modelly"),
    ("mesa", "modelly"),
)

# (regex, replacement) applied line by line after the import rewrite.
LINE_REWRITES = (
    (
        re.compile(
            r"super\(\)\.__init__\(\s*(?:unique_id|self\.next_id\(\)|model\.next_id\(\))\s*,\s*model\s*\)"
        ),
        "super().__init__(model)",
    ),
    (re.compile(r"\b(\w+)\.schedule\.steps\b"), r"\1.time"),
    (re.compile(r"\b(\w+)\.schedule\.agents\b"), r"\1.agents"),
    (re.compile(r"\b(\w+)\.schedule\.get_agent_count\(\)"), r"len(\1.agents)"),
    (re.compile(r"\b(\w+)\.schedule\.step\(\)"), r'\1.agents.shuffle_do("step")'),
)

# (regex, reason, guide section) for lines that need a decision.
FLAGS = (
    (
        re.compile(
            r"\b(RandomActivation(?:ByType)?|StagedActivation|SimultaneousActivation|BaseScheduler)\b"
        ),
        "scheduler class: replace with AgentSet activation",
        "activation-and-schedulers",
    ),
    (
        re.compile(r"\bself\.schedule\.(add|remove)\("),
        "schedule.add/remove: delete, agents register themselves",
        "activation-and-schedulers",
    ),
    (
        re.compile(r'shuffle_do\("step"\)'),
        "rewritten from schedule.step(): check the activation order you need",
        "activation-and-schedulers",
    ),
    (
        re.compile(r"\b(MultiGrid|SingleGrid|NetworkGrid)\("),
        "legacy grid: use the cell space",
        "grids-and-positions",
    ),
    (
        re.compile(
            r"\.(place_agent|move_agent|move_to_empty|get_neighbors|get_neighborhood|get_cell_list_contents|is_cell_empty|coord_iter|out_of_bounds)\("
        ),
        "legacy grid call: use cells",
        "grids-and-positions",
    ),
    (
        re.compile(r"\bself\.pos\b"),
        "agent.pos: use self.cell.coordinate",
        "grids-and-positions",
    ),
    (
        re.compile(r"\bPropertyLayer\("),
        "PropertyLayer: use grid.create_property_layer",
        "grids-and-positions",
    ),
    (
        re.compile(r"def __init__\(\s*self\s*,\s*unique_id\b"),
        "unique_id parameter: Modelly assigns ids, remove it here and at the callers",
        "agents",
    ),
    (re.compile(r"\.next_id\(\)"), "next_id(): delete, ids are automatic", "agents"),
    (
        re.compile(r"\bbatch_run\("),
        "batch_run: use scenarios and run_scenarios",
        "batch-runs",
    ),
    (
        re.compile(r"\b(ABMSimulator|DEVSimulator)\b"),
        "simulator: schedule on the model instead",
        "events-and-simulators",
    ),
    # Keyword form only (``seed=42``): a ``seed = ...`` assignment is the user's own variable.
    (re.compile(r"\bseed=(?!=)"), "seed=: Model and Scenario take rng=", "model"),
    (re.compile(r"\bself\.steps\b"), "self.steps: use self.time", "model"),
    # Rewritten by the catch-all mapping, but Modelly has no such module.
    (
        re.compile(r"\bmodelly\.(experimental|space\.property_layer)\b"),
        "Mesa module with no Modelly equivalent: see the guide",
        "imports",
    ),
    (
        re.compile(r"\bModularServer\b|\bmesa\.visualization\.modules\b"),
        "Mesa 2 visualization: rewrite with SolaraViz",
        "visualization",
    ),
)
