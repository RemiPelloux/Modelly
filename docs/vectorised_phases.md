# Vectorised step phases: when a loop over agents is an array operation

Modelly keeps agents as objects and moves the bulk of a step into arrays:
`Column` state, `ColumnTable.draw` / `do_where` / `remove_where` / `thin`,
`CellIndex` and `Occupancy` / `claim` for any discrete space, `pairs_within` /
`move_all` for continuous space. A model written this way runs a different *program* from the per-agent
loop, so it has to be the same *model*. This page states when it is, and how
the claim is checked in the benchmark playbooks.

The setting throughout: a step phase in which every agent `i` draws its own
randomness and updates its own state from a snapshot of the model taken at the
start of the phase (synchronous update). Random-activation models whose agents
read state that other agents wrote earlier in the same phase are a different
model, and the playbooks are written synchronously on both frameworks for that
reason.

## 1. Independent draws commute with order (the Bernoulli phase)

**Claim.** Let agent `i` perform action `A_i` with probability `p_i`, the draws
independent, and let `A_i` read only the start-of-phase snapshot and write only
agent `i`'s own state. Then the per-agent loop in any order, shuffled or not,
and the vectorised form

```python
mask = table.draw(p)  # one Bernoulli vector, p a scalar or one p_i per row
table.do_where(mask, "A")  # or remove_where(mask), or a column write
```

produce the same joint distribution of the end-of-phase state.

**Why.** The end state is a deterministic function of the snapshot and the
vector of outcomes `(X_1, …, X_n)`, since no action reads another's write. In
both programs the `X_i` are independent Bernoulli(`p_i`) variables: the loop
draws them one at a time from one generator, the vector form draws them in one
call. Same distribution of the inputs to the same function gives the same
distribution of the output. Order of evaluation, and therefore the shuffle,
plays no role. A loop that short-circuits (for instance, stops testing
cellmates after the first success) still draws each `X_i` from the stated law.

Used by: every `draw` / `do_where` / `remove_where` phase in the playbooks
(deaths, reproduction, recovery, resistance, laying).

## 2. Contact aggregation (exposure to k independent sources)

**Claim.** A susceptible agent that has `k` infected contacts, each infecting it
independently with probability `β`, becomes infected with probability

```
p(k) = 1 - (1 - β)^k
```

and, given the start-of-phase configuration, the infections of different
susceptibles are independent.

**Why.** It escapes all `k` attempts with probability `(1-β)^k`. Each pair
(source, target) has its own coin and no coin is shared between two targets, so
conditional on the configuration the targets' outcomes are independent. With
§1 this makes the whole infection phase one draw with `p = 1 - (1-β)**k`.

`k` itself is an array: for same-cell contact it is
`index.counts(rows, infected)[rows]`, a `bincount`; for contact along the
connections of any discrete space it is `index.neighbor_sum(infected_per_cell)`,
one sparse matrix-vector product over the CSR adjacency that `CellIndex` builds
once from the cells' `connections`. Used by: `grid_epidemic`, `network_contagion`.

## 3. Uniform tie-breaking by a random permutation

**Claim.** When at most one agent per cell may take a resource ("the first sheep
in the shuffled order eats the grass"), the winner is uniformly distributed
among the cell's candidates. Permuting the candidate rows with
`rng.permutation` and keeping the first occurrence of each cell
(`np.unique(rows[order], return_index=True)`) picks the winner with the same
law, independently across cells.

**Why.** A uniform random permutation restricted to the candidates of one cell
is a uniform permutation of them, so its first element is uniform; the
restrictions to different cells are independent given the cell membership.
Used by: `predator_prey` grazing.

## 4. Movement as a column, occupancy from a sort

An agent whose cell is a column of cell rows moves by assignment:
`table.row = index.random_neighbor(table.row, rng)` moves every agent to a
uniformly chosen neighbouring cell, the same law as "pick a random cell of my
neighbourhood" one agent at a time (§1 with the move as the action, since no
move reads another agent's move). No cell keeps a list of its agents. When a
phase needs the cellmates, `Occupancy(table.row, n_cells)` sorts the rows once
and answers "who is in cell c" and "a random member of cell c" from the sorted
order, O(n log n) per step instead of a list update per move.

Agents placed this way are in no cell's agent list, so declare them to the
index for the space and the visualisation: `index.track(model, Person,
column="row")`. `space.agents` then lists them after the cell-list agents, and
the renderers place each one at `index.cells[agent.row]`.

**Claim (claim with retry).** Let claimants act in a uniformly random order and
each take a uniformly random member of its cell not yet taken. Then in every
cell exactly min(claimants, members) are taken, the taken members form a
uniform random subset of the cell's members, and the served claimants a
uniform random subset of its claimants. `claim(occupancy, cells, rng)` draws
for every unserved claimant a uniformly random member of its cell, rejects
draws of taken members, resolves collisions in favour of a uniformly random
priority, and repeats while a claimant still has a free member; it produces a
matching with the same law.

**Why.** Both procedures treat the members of a cell symmetrically and the
claimants of a cell symmetrically, so the law of the matching is invariant
under relabelling either side; the only such law on injections of a fixed size
is the uniform one, and the size is min(claimants, members) in both since each
stops only when no claimant has a free member. The rejection step keeps every
draw uniform over the free members, so no round biases the outcome. Used by:
`predator_prey`, wolves eating sheep.

## 5. Cohort compression (super-individuals) by binomial thinning

**Claim.** Consider `n` individuals in the same state whose next state depends
only on that shared state, on model-level quantities fixed for the phase, and
on an independent draw each. Represent them as one cohort with `count = n`.
Then:

- survival with probability `s`: `count ~ Binomial(n, s)` has the law of the
  number of individual survivors, because a sum of `n` independent
  Bernoulli(`s`) variables is Binomial(`n`, `s`) (`ColumnTable.thin`);
- a binary attribute drawn at a transition (sex at emergence, fertile mating):
  the split `(Binomial(n, q), n - Binomial(n, q))` has the law of the counts of
  the two individual outcomes;
- an event each member triggers independently with probability `q`, each
  producing a fixed number `c` of offspring in a common state: the offspring
  count `c · Binomial(n, q)` has the law of the individual-level total, and the
  offspring form one new cohort because they share one state.

By induction over phases and days, the vector of per-state counts of the
cohort model has the same distribution as that of the individual model, for
any history. What is lost is only individual identity, which the individual
model never used.

**Scope.** Cohorts must stay homogeneous: every member must face the same
probabilities at every phase. Stage durations that are fixed numbers of days,
daily survival that depends on stage and on a model-level density, and
fecundity that depends on stage and age in stage all keep a cohort
homogeneous. A per-individual continuous trait (body size, position) breaks it
unless the cohorts are keyed on that trait too. Used by: `insect_cohorts`,
variant `modelly-cohorts`, against the individual-level `modelly` and `mesa`
variants.

## 6. Neighbour search in continuous space

Not a distributional claim but a cost one. For `n` agents and a query radius
`r`, `ContinuousSpace.neighbors_within(r)` and `pairs_within(space, r)` build
one KD-tree (`O(n log n)`) and answer every query from it; asking each agent in
turn with a scan of all positions costs `O(n²)`. The two return the same
neighbour relation (points at distance exactly `r` aside), as the
`flocking` playbook shows: both implementations compute identical headings to
machine precision from the same initial state.

## How the playbooks check the claims

`benchmarks/playbooks/compare.py` runs every implementation of a playbook on
the same list of seeds and compares each summary statistic against the Mesa
reference with Welch's t-test; a p-value below 0.01 is flagged in the results.
It also runs the first seed twice per implementation to confirm determinism.
The distributions, not the samples, are what the theorems above say must
match: the implementations draw their random numbers in different orders and
from different generators, so their outputs differ run by run and agree in
law. Timing a port that matches the random stream bit for bit is a separate
method, described in [performance.md](performance.md).
