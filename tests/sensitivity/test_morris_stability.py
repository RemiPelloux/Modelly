"""Morris screening ranks the top parameters of zoo models the same on every seed.

Two zoo models, each with parameters whose effects are well apart and one that
barely matters:

- Bass diffusion, adoption after six years: innovation, then imitation, then the
  number of households (a share hardly depends on it); the whole ranking holds;
- the age-structured SEIR model, share recovered after 60 steps: the transmission
  probability first, by a factor of three or more; the recovery and incubation
  probabilities have effects of the same size in these ranges, so only the top
  parameter is checked.

Each seed draws other Morris trajectories and other model runs (12 trajectories,
``12 * (parameters + 1)`` runs).
"""

import pytest

from modelly.experiments import ScenarioSpace
from modelly.experiments.space import Fixed
from modelly.sensitivity import morris
from modelly.zoo.age_seir.model import AgeSEIR, State
from modelly.zoo.bass_diffusion.model import BassDiffusion

pytest.importorskip("pyarrow")

SEEDS = (1, 2, 3, 4, 5)
TRAJECTORIES = 12
STEPS = 60
SEPARATION = 2  # the top parameter's mu* is at least this many times any other's

BASS = ScenarioSpace(
    innovation=(0.005, 0.08), imitation=(0.2, 0.5), households=(1000, 3000)
)
BASS_RANKING = ["innovation", "imitation", "households"]
SEIR = ScenarioSpace(
    beta=(0.02, 0.06),
    recovery=(0.15, 0.3),
    incubation=(0.2, 0.5),
    group_sizes=Fixed((2000, 6000, 2000)),
    initial_infected=Fixed((5, 5, 5)),
)
SEIR_TOP = "beta"


def recovered_share(model: AgeSEIR) -> float:
    """The share of the population recovered, all age groups together."""
    counts = model.counts()
    return float(counts[:, State.R].sum() / counts.sum())


def screen(model, space, output, seed):
    """Morris on ``model`` for ``seed``: its mu* by parameter, largest first."""
    result = morris(
        model, space, output, trajectories=TRAJECTORIES, steps=STEPS, seed=seed
    )
    return result.table["mu_star"].sort_values(ascending=False)


@pytest.mark.parametrize("seed", SEEDS)
def test_bass_diffusion_ranking_is_the_same_on_every_seed(seed):
    """Innovation, imitation, households: the whole ranking, whatever the seed."""
    mu_star = screen(BassDiffusion, BASS, "adoption", seed)
    assert list(mu_star.index) == BASS_RANKING
    assert mu_star.iloc[0] > SEPARATION * mu_star.iloc[1]


@pytest.mark.parametrize("seed", SEEDS)
def test_age_seir_top_parameter_is_the_same_on_every_seed(seed):
    """Transmission comes first, well ahead of recovery and incubation."""
    output = f"{__name__}:recovered_share"
    mu_star = screen(AgeSEIR, SEIR, output, seed)
    assert mu_star.index[0] == SEIR_TOP
    assert mu_star.iloc[0] > SEPARATION * mu_star.iloc[1]


def test_seeds_change_the_screen():
    """The seeds really differ: the indices are not the same numbers every time."""
    first = screen(BassDiffusion, BASS, "adoption", SEEDS[0])
    second = screen(BassDiffusion, BASS, "adoption", SEEDS[1])
    assert not first.equals(second)
