"""Smoke test: one season per crop, both frameworks, compared by hand.

Usage (each in its own venv):
    .venv-mesa2/bin/python benchmarks/mesaVSmodelly/smoke.py \
        benchmarks/mesaVSmodelly/mesa/Notebook_ABM_TIS_Optimise.ipynb step
    .venv/bin/python benchmarks/mesaVSmodelly/smoke.py \
        benchmarks/mesaVSmodelly/modelly/Notebook_ABM_TIS_Optimise_Modelly.ipynb advance_day
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    nb_path = Path(sys.argv[1])
    step_fn = sys.argv[2]  # "step" for mesa, "advance_day" for modelly

    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    namespace: dict = {"__name__": "__smoke__"}
    for i in range(5):  # cells 0-4: imports, crops, lifespan, agents, model
        exec(compile(cells[i], f"<cell {i}>", "exec"), namespace)  # noqa: S102

    RM, STRAWBERRY, CHERRY = (
        namespace["RematingModel"],
        namespace["STRAWBERRY"],
        namespace["CHERRY"],
    )

    result: dict = {}
    for name, crop in (("strawberry", STRAWBERRY), ("cherry", CHERRY)):
        model = RM(
            crop_parameters=crop, num_agents_wild=10, num_agents_females=10, seed=42
        )
        for _ in range(crop.season_length):
            getattr(model, step_fn)()

        df = model.get_model_dataframe()
        result[name] = {
            "df_sha256": hashlib.sha256(df.to_csv(index=False).encode()).hexdigest(),
            "df_rows": len(df),
            "harvested_fruits": model.cumulative_harvested_fruits,
            "harvested_clean": model.cumulative_harvested_clean,
            "harvested_sterile_only": model.cumulative_harvested_sterile_only,
            "harvested_with_larvae": model.cumulative_harvested_with_larvae,
            "rotten_fruits": model.cumulative_rotten_fruits,
            "rotten_with_larvae": model.cumulative_rotten_with_larvae,
            "rotten_sterile_only": model.cumulative_rotten_sterile_only,
            "rotten_clean": model.cumulative_rotten_clean,
            "larvae_born": model.cumulative_larvae_born,
            "final_agents": len(model.agents),
            "final_fruits": len(model.fruits),
        }

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
