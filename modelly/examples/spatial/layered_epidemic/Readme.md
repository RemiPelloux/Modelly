# Layered Epidemic

An age-structured SIR epidemic on a three-layer contact network, built with
`modelly.space.networks`:

- **household**: everybody in a household is in contact (weight 1);
- **school**: children are shuffled into classes, everybody in a class is in contact
  (weight 0.5);
- **work**: adults of working age are shuffled into small workplaces (weight 0.25).

The three layers share one `MultilayerNetwork`. Each step, the infection pressure on every
person is one sparse product, `network.adjacency() @ infected`, where the adjacency sums the
layers with their weights. A susceptible person is infected with probability
`1 - exp(-beta * pressure)`; an infected person recovers with probability `recovery`.

When the share infected reaches `close_schools_at`, the schools close:
`network.add_layer("school", 0.0)` sets the layer's weight to zero without touching its
edges, so reopening is one more call.

`model.contacts` is the age-group contact matrix of the network at the start
(`contact_matrix`), the input a compartmental model would need; `attack_rate_by_group()`
gives the share of children, adults and seniors ever infected. The mean number of contacts is
recorded with `network_reporter("network", mean_degree)`, a reporter that survives
checkpoints.

## How to run

```bash
python -c "from modelly.examples.spatial.layered_epidemic.model import LayeredEpidemic; m = LayeredEpidemic(); m.run_for(60); print(m.datacollector.get_model_vars_dataframe().tail())"
```
