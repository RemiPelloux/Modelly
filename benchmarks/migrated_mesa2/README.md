# Same code on both frameworks: two Mesa 2.3 playbooks migrated by the codemod

`benchmarks/playbooks/<playbook>/mesa_model.py` is the Mesa 2.3 reference; the file of the same
name here is the same model migrated to Modelly, made by `python -m modelly.migrate --write` and then by the
manual steps the codemod reports, and nothing else:

- the agents' `unique_id` parameter and the `next_id()` calls are removed (Modelly assigns ids);
- `super().__init__(seed=seed)` becomes `super().__init__(rng=seed)`, followed by
  `self.random = modelly.FastRandom(seed)`, the stream Mesa 2.3 builds from `seed`;
- for Boltzmann wealth, Mesa 2.3's `RandomActivation`, which reshuffles one persistent order in
  place every step, becomes a persistent `AgentSet` reshuffled in place
  (`self.order.shuffle(inplace=True).do("step")`).

Every line of model logic is unchanged. The migrated models produce bit-identical statistics to the Mesa
2.3 references on every seed tried (20 at the small size, 5 at the large size). The other six
playbooks use Mesa 2's legacy grids (`MultiGrid`, `SingleGrid`, `ContinuousSpace`,
`NetworkGrid`), which Modelly does not provide: migrating them means rewriting the space, so they
cannot be migrated line for line.

The paired timing is `paper/data/migrated.json` (fresh interpreter per run, ten alternating
rounds, pinned to one core).
