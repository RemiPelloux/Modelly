"""The playbooks: one workload each, with the same parameters for every implementation.

Every playbook directory holds one module per implementation. Each module
exposes ``build(seed, **params) -> model`` and
``simulate(model, steps) -> {"population": int, "stats": {...}}`` and must be
deterministic for a given seed. The ``mesa`` variant is the
reference the others are checked against.
"""

PLAYBOOKS = {
    "grid_epidemic": {
        "title": "Synchronous SIR epidemic on a torus grid",
        "variants": {
            "mesa": "mesa_model",
            "modelly-cells": "modelly_cells",
            "modelly": "modelly_model",
        },
        "steps": 60,
        "sizes": {
            "small": {"n": 2000, "side": 60},
            "large": {"n": 20000, "side": 180},
        },
        "params": {"beta": 0.25, "recovery": 10, "initially_infected": 20},
    },
    "predator_prey": {
        "title": "Predator-prey with grass regrowth: births and deaths every step",
        "variants": {
            "mesa": "mesa_model",
            "modelly-cells": "modelly_cells",
            "modelly": "modelly_model",
        },
        "steps": 200,
        "sizes": {
            "small": {"side": 80, "sheep": 240, "wolves": 16},
            "large": {"side": 200, "sheep": 1500, "wolves": 100},
        },
        "params": {
            "sheep_reproduce": 0.04,
            "wolf_reproduce": 0.03,
            "sheep_gain": 4.0,
            "wolf_gain": 40.0,
            "regrowth": 20,
        },
    },
    "flocking": {
        "title": "Flocking in continuous space, simultaneous update",
        "variants": {"mesa": "mesa_model", "modelly": "modelly_model"},
        "steps": 50,
        "sizes": {
            "small": {"n": 500, "side": 100.0},
            "large": {"n": 4000, "side": 300.0},
        },
        "params": {
            "vision": 10.0,
            "speed": 1.0,
            "separation": 2.0,
            "cohere": 0.03,
            "separate": 0.015,
            "match": 0.05,
        },
    },
    "network_contagion": {
        "title": "Virus on a random network with recovery and resistance",
        "variants": {"mesa": "mesa_model", "modelly": "modelly_model"},
        "steps": 100,
        "sizes": {"small": {"n": 2000}, "large": {"n": 30000}},
        "params": {
            "avg_degree": 6,
            "beta": 0.15,
            "gamma": 0.1,
            "resistance": 0.5,
            "outbreak": 0.01,
        },
    },
    "insect_cohorts": {
        "title": "Stage-structured insect population under sterile releases",
        "variants": {
            "mesa": "mesa_model",
            "modelly": "modelly_model",
            "modelly-cohorts": "modelly_cohorts",
        },
        "steps": 120,
        "sizes": {
            "small": {"initial_adults": 100, "capacity": 5000},
            "large": {"initial_adults": 500, "capacity": 50000},
        },
        "params": {
            "egg_days": 3,
            "larva_days": 8,
            "pupa_days": 10,
            "maturity_days": 5,
            "survival": {"egg": 0.9, "larva": 0.95, "pupa": 0.97, "adult": 0.95},
            "lay_prob": 0.5,
            "clutch": 8,
            "sterile_ratio": 1.0,
        },
    },
    "schelling": {
        "title": "Schelling segregation: unhappy residents move to random empty cells",
        "variants": {
            "mesa": "mesa_model",
            "modelly-cells": "modelly_cells",
            "modelly": "modelly_model",
        },
        "steps": 40,
        "sizes": {"small": {"side": 40}, "large": {"side": 200}},
        "params": {"density": 0.8, "minority": 0.3, "homophily": 3},
    },
}
