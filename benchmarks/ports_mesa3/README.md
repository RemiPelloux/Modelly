# Same code on both frameworks: five playbooks ported from Mesa 3.5

`benchmarks/playbooks/<playbook>/mesa3_model.py` is the Mesa 3.5 implementation; the file of the
same name here is its port to Modelly, made by `python -m modelly.migrate --write` and nothing
else. The codemod rewrites the imports (`mesa` to `modelly`, `mesa.discrete_space` to
`modelly.space`) and the base classes (`mesa.Agent`, `mesa.Model`, `mesa.DataCollector`, the
cell spaces and their agents); no line of model logic changes.
`diff ../playbooks/<playbook>/mesa3_model.py <playbook>/mesa3_model.py` shows the whole port.

The ports are not bit-identical to the originals. Modelly derives `model.random` from the seed
differently from Mesa 3.5, so the same seed gives a different random stream and a different
run. They agree in distribution instead: over 100 shared seeds at the small size, 24 of the 26 summary statistics are
equivalent within half a standard deviation (TOST at 5%), and no paired or Kolmogorov-Smirnov
test is significant after a Holm correction.

The ported playbooks are grid epidemic, virus on a network, insects (individuals), Schelling
and Boltzmann wealth. The other three do not port by the codemod alone:

- flocking uses Mesa's legacy `mesa.space.ContinuousSpace`, which Modelly does not provide;
- predator-prey and Sugarscape keep their grass and sugar in Mesa 3.5's `PropertyLayer`, whose
  API Modelly does not reproduce (Modelly's layers are plain numpy arrays).

The paired timing and the agreement study are in `paper/data/port_public.json` (keys `mesa3`
and `mesa3_agreement`), written by `paper/scripts/ports.py` (fresh interpreter per run, ten
alternating rounds, pinned to one core). The ports run at 0.46 (Boltzmann), 0.55 (insects),
0.76 (grid epidemic), 0.82 (network) and 0.99 (Schelling) of Mesa 3.5's CPU time for the steps.
