# Epidemic coupled to hospital capacity

**Field:** epidemiology · **Zoo name:** `hospital_epidemic` · **Module:** `modelly.zoo.hospital_epidemic.model`

![Occupied and open beds over time, with and without the contact response](https://remipelloux.github.io/Modelly/_images/hospital_epidemic.png)

People are agents, each susceptible, infectious or recovered, mixing homogeneously. A susceptible is infected in a step with probability `1 - exp(-beta_eff * I / N)`, an infectious person recovers with probability `recovery` per step, and a share `severe` of the new infections need a hospital bed. The hospital is a system-dynamics model: occupied beds fill with the admissions and empty at rate `occupied / stay`; open beds move towards `base_beds + surge * occupied` with time constant `ramp`, as a hospital opens surge wards. People respond to the pressure on the hospital: their contacts fall with the share of beds occupied, `beta_eff = beta / (1 + response * occupied / beds)`.

## How it is written

People are `Person` agents with a `Column` for their state, so a step is a few numpy operations on the whole population. The hospital is a [`StockFlow`](https://remipelloux.github.io/Modelly/coupling.html) with two stocks and three flows, integrated with scipy’s `solve_ivp` (Dormand-Prince, `rtol=1e-8`):

Flow

From

To

Rate

admit

outside

occupied

the admissions of the agents’ step

discharge

occupied

outside

occupied / stay

open

outside

beds

(base_beds + surge * occupied - beds) / ramp (negative: closing)

A `Coupling` runs the agents in phase 0 (they read `occupied` and `beds` and write `admissions`) and the hospital in phase 1 (it reads `admissions` and writes the stocks), so the agents see the hospital as it was at the end of the previous step.

```python
from modelly.zoo.hospital_epidemic.model import HospitalEpidemic, HospitalScenario

model = HospitalEpidemic(HospitalScenario(rng=42, response=2.0))
model.run()
model.attack_rate(), model.final_size()  # the second ignores the response
model.hospital.state, model.hospital.totals  # stocks, and what each flow has moved
model.datacollector.get_model_vars_dataframe()  # S, I, R, admissions, occupied, beds
```

Parameter

Default

Meaning

population

20000

number of people

initial_infected

20

infectious people at the start

beta

0.3

transmission rate per step (R0 = beta / recovery)

recovery

0.1

recovery probability per step

severe

0.02

share of new infections admitted

stay

8.0

mean length of stay, in steps

base_beds

40.0

beds open when the hospital is empty

surge

0.5

beds opened per occupied bed

ramp

7.0

time constant of opening and closing beds

response

1.0

how strongly contacts fall with the share of beds occupied

steps

300

run length of run()

## Validation

Three known answers:

- **Final size.** Without the response the agents are the stochastic general epidemic, whose attack rate solves `s = s0 exp(-R0 (1 - s))` with `R0 = beta / recovery`. The test checks it for three seeds, within five standard deviations of the final-size central limit theorem (Andersson and Britton, 2000).
- **The hospital’s exact solution.** Its equations are linear, so for the admissions of each step, held over the step, the matrix exponential of the augmented system gives occupancy and beds exactly. The integrated values match it within `1e-6` over 300 steps, with and without the response.
- **Mass balance.** Every admitted patient is still in hospital or has been discharged: the admissions the agents wrote equal `occupied + discharged` to round-off, and the beds equal `base_beds` plus the net amount opened.

`tests/zoo/test_hospital_epidemic.py` also checks that a stronger response lowers the peak occupancy and the attack rate, that the population is conserved, that a run resumed from a checkpoint is identical, bit for bit, to a straight one, and that the same seed gives the same run.

## Model card: Epidemic coupled to hospital capacity

SIR agents whose severe cases fill a hospital stock-flow model that opens surge beds, while the pressure on beds feeds back to lower contacts.

**Model:** `modelly.zoo.hospital_epidemic.model:HospitalEpidemic` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `510d3871dec9`

### Intended use

- Teaching how an agent-based epidemic couples to a system-dynamics model: admissions flow one way, bed pressure the other, with a lag of one step.
- Comparing scenarios in relative terms: how surge capacity, length of stay or the strength of the contact response change peak occupancy and the attack rate.
- A starting point for epidemic and health-system models, with a validated epidemic core, an exactly checked hospital and a closed mass balance.

### Out-of-scope use

- Forecasting bed demand for a real hospital or health system: the rates, the severe share and the bed numbers are illustrative and nothing is calibrated.
- Capacity or triage decisions for a specific hospital without its own admission, stay and staffing data.
- Epidemics whose natural history is not SIR with geometric periods, or where severity depends on age or other attributes.

### Data

- None by default: the population of 20,000, the transmission and recovery rates, the 2 % severe share and the hospital parameters are illustrative values in `HospitalScenario`.

### Validation

Check

Test

without the response, the attack rate is within five standard deviations of the final-size relation (three seeds)

tests/zoo/test_hospital_epidemic.py::test_final_size_relation_without_response

occupancy and beds match the exact matrix-exponential solution within 1e-6, with and without the response

tests/zoo/test_hospital_epidemic.py::test_hospital_matches_the_exact_linear_solution

admissions equal patients in hospital plus those discharged, to round-off, and beds equal base beds plus the net amount opened

tests/zoo/test_hospital_epidemic.py::test_admissions_balance_occupancy_and_discharges

a stronger response lowers peak occupancy and the attack rate; people are conserved; a resumed checkpoint is identical; same seed, same run

tests/zoo/test_hospital_epidemic.py

### Known limits

- Homogeneous mixing: no households, places or networks, and everyone responds to bed pressure in the same way.
- Admitted patients only occupy beds and are discharged at rate `occupied / stay`; there are no deaths, no staff limits and no turned-away patients when beds run out.
- One step is one unit of time with transitions drawn once per step, and the hospital sees each step’s admissions held constant over that step.
- Closed population with no births, deaths or waning immunity; the final-size check holds only without the contact response.

### Ethical considerations

- Results about bed capacity and contact reductions bear on decisions that affect patients and health workers; present them as illustrative, with the assumptions above, never as a forecast.
- The contact response is one illustrative rule; do not read it as a measured behaviour of any population.

## References

- Kermack, W. O. and McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. *Proceedings of the Royal Society A*, 115, 700-721.
- Andersson, H. and Britton, T. (2000). *Stochastic Epidemic Models and Their Statistical Analysis*. Lecture Notes in Statistics 151, Springer.
- Sterman, J. D. (2000). *Business Dynamics: Systems Thinking and Modeling for a Complex World*. Irwin/McGraw-Hill.

Start a project from it with `modelly zoo copy hospital_epidemic my_hospital`.
