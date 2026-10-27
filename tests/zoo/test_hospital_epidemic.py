"""Epidemic and hospital: final size, the exact hospital solution and its mass balance."""

import numpy as np
import pytest
from scipy.linalg import expm

from modelly.zoo.hospital_epidemic.model import (
    HospitalEpidemic,
    HospitalScenario,
    Person,
    State,
)

SEEDS = (11, 12, 13)
# Five standard deviations of the final-size CLT: no fixed-seed run should get near it.
Z_BOUND = 5.0
# solve_ivp at rtol 1e-8 per step, over 300 steps.
SOLVER_TOLERANCE = 1e-6
# Round-off on sums of a few hundred admissions.
ROUND_OFF = 1e-12


def run(seed, **changes):
    """A finished run and its model-variable frame."""
    model = HospitalEpidemic(HospitalScenario(rng=seed, **changes))
    model.run()
    return model, model.datacollector.get_model_vars_dataframe()


def final_size_sd(model):
    """Standard deviation of the attack rate (Andersson and Britton's final-size CLT).

    ``sigma^2 = tau (1 - tau) (1 + cv^2 R0^2 (1 - tau)) / (1 - R0 (1 - tau))^2`` over the
    population size, with ``cv^2 = 1 - recovery`` for the geometric infectious period.
    """
    tau, r0 = model.final_size(), model.r0()
    cv2 = 1.0 - model.scenario.recovery
    escape = 1.0 - tau
    var = tau * escape * (1 + cv2 * r0**2 * escape) / (1 - r0 * escape) ** 2
    return np.sqrt(var / model.scenario.population)


def exact_hospital(scenario, admissions):
    """Occupancy and beds from the matrix exponential, step by step.

    ``d[H, B]/dt = M [H, B] + c`` with ``M = [[-1/stay, 0], [surge/ramp, -1/ramp]]`` and
    ``c = [a, base/ramp]``; the augmented matrix ``[[M, c], [0, 0]]`` propagates one step.
    """
    s = scenario
    state = np.array([0.0, s.base_beds, 1.0])
    path = [state[:2].copy()]
    for a in admissions:
        system = np.array(
            [
                [-1 / s.stay, 0.0, a],
                [s.surge / s.ramp, -1 / s.ramp, s.base_beds / s.ramp],
                [0.0, 0.0, 0.0],
            ]
        )
        state = expm(system) @ state
        path.append(state[:2].copy())
    return np.array(path)


@pytest.mark.parametrize("seed", SEEDS)
def test_final_size_relation_without_response(seed):
    """The attack rate solves ``s = s0 exp(-R0 (1 - s))`` within the CLT bound."""
    model, _ = run(seed, response=0.0)
    assert model.counts()[State.I] == 0  # the epidemic is over
    assert model.r0() == pytest.approx(3.0)
    assert abs(model.attack_rate() - model.final_size()) < Z_BOUND * final_size_sd(
        model
    )


@pytest.mark.parametrize("response", [0.0, 1.0])
def test_hospital_matches_the_exact_linear_solution(response):
    """Integrated occupancy and beds equal the matrix-exponential solution."""
    model, frame = run(14, response=response)
    exact = exact_hospital(model.scenario, frame["admissions"].iloc[1:].to_numpy())
    simulated = frame[["occupied", "beds"]].to_numpy()
    assert np.allclose(simulated, exact, rtol=SOLVER_TOLERANCE, atol=SOLVER_TOLERANCE)
    assert frame["occupied"].max() > model.scenario.base_beds  # the surge was needed


@pytest.mark.parametrize("seed", SEEDS)
def test_admissions_balance_occupancy_and_discharges(seed):
    """Every admitted patient is in hospital or discharged, to round-off."""
    model, frame = run(seed)
    hospital = model.hospital
    occupied = hospital.state["occupied"]
    totals = hospital.totals
    assert frame["admissions"].sum() == model.admitted
    assert totals["admit"] == pytest.approx(model.admitted, rel=ROUND_OFF)
    assert occupied + totals["discharge"] == pytest.approx(
        model.admitted, rel=ROUND_OFF
    )
    beds = model.scenario.base_beds + totals["open"]
    assert hospital.state["beds"] == pytest.approx(beds, rel=ROUND_OFF)


@pytest.mark.parametrize("seed", SEEDS)
def test_hospital_pressure_flattens_the_curve(seed):
    """A stronger response to occupancy lowers the peak and the attack rate."""
    peaks, attacks = [], []
    for response in (0.0, 1.0, 3.0):
        model, frame = run(seed, response=response)
        peaks.append(frame["occupied"].max())
        attacks.append(model.attack_rate())
    assert peaks == sorted(peaks, reverse=True)
    assert attacks == sorted(attacks, reverse=True)


def test_people_are_conserved():
    """S + I + R is the population at every step."""
    model, frame = run(15, steps=60)
    assert (frame[["S", "I", "R"]].sum(axis=1) == model.scenario.population).all()
    assert len(model.columns[Person]) == model.scenario.population


def test_checkpoint_resumes_bit_for_bit(tmp_path):
    """Save at step 40, load, run 40 more: the same frame and hospital as 80 straight."""
    straight, frame = run(16, steps=80)
    model = HospitalEpidemic(HospitalScenario(rng=16))
    model.run(40)
    model.save(tmp_path / "hospital.ckpt")
    resumed = HospitalEpidemic.load(tmp_path / "hospital.ckpt")
    resumed.run(40)
    assert resumed.datacollector.get_model_vars_dataframe().equals(frame)
    assert np.array_equal(resumed.hospital.y, straight.hospital.y)


def test_same_seed_same_run():
    """Same seed, same curves; another seed, other curves."""
    assert run(17, steps=60)[1].equals(run(17, steps=60)[1])
    assert not run(17, steps=60)[1].equals(run(18, steps=60)[1])
