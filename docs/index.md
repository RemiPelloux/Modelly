---
myst:
  html_meta:
    description: "Modelly is an agent-based modeling (ABM) framework for Python: typed scenarios, seeded reproducible runs, numpy-backed agents, grids, networks, continuous space, discrete-event time, pandas data collection and browser visualization."
    keywords: "agent-based modeling, ABM, agent-based simulation, Python, multi-agent systems, complex systems, discrete-event simulation, Mesa alternative"
    "og:title": "Modelly: agent-based modeling in Python"
    "og:description": "Build, run, measure and replay agent-based models in Python. Fast by construction, reproducible by default."
    "og:type": "website"
---

# Modelly: agent-based modeling in Python

<div class="ml-landing">
<section class="ml-hero" aria-labelledby="ml-hero-title">
<div class="ml-hero-grid">
<div>
<p class="ml-hero-title" id="ml-hero-title" role="heading" aria-level="2">Agent-based models in Python, fast enough to explore.</p>
<p class="ml-hero-sub">Modelly is an open-source framework for agent-based modeling. Write agents with a <code>step()</code>, keep their state in numpy columns as the model grows, and get the same result from the same seed every time.</p>
<div class="ml-actions">
<a class="ml-btn ml-btn-primary" href="tutorials/0_first_model.html">Build your first model</a>
<a class="ml-btn ml-btn-ghost" href="#ml-bench-title">See the benchmarks</a>
</div>
<button type="button" class="ml-pip" data-copy="pip install modelly-abm" aria-label="Copy the install command"><span>$</span> pip install modelly-abm <em>Copy</em></button>
</div>
<figure class="ml-lab" aria-label="A live epidemic simulation">
<span class="ml-hint">Click or drag to infect cells</span>
<canvas class="ml-lab-world" role="img" aria-label="Grid of cells: blue susceptible, pink infected, green recovered"></canvas>
<canvas class="ml-lab-curve" role="img" aria-label="Share of infected and recovered cells over time"></canvas>
<figcaption class="ml-lab-bar">
<span class="ml-legend"><span><i class="ml-dot" style="background:#6c8cff"></i>Susceptible<b data-out="s">0</b></span><span><i class="ml-dot" style="background:#ff4f8b"></i>Infected<b data-out="i">0</b></span><span><i class="ml-dot" style="background:#2fd4a7"></i>Recovered<b data-out="r">0</b></span></span>
<span class="ml-legend"><label class="ml-ctl">Transmission <input type="range" min="0.04" max="0.4" step="0.01" value="0.10" data-beta> <b data-out="beta">0.10</b></label><span>Step <b data-out="tick">0</b></span><button type="button" class="ml-btn ml-btn-ghost ml-btn-small" data-toggle>Pause</button></span>
</figcaption>
</figure>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-bench-title">
<div class="ml-wrap">
<h2 id="ml-bench-title">The same models, 5 to 244 times faster than Mesa</h2>
<p class="ml-lede">Five playbooks, each written twice in the idiom of its framework. Median CPU seconds of the steps over three rounds, a fresh interpreter per run, pinned to one core.</p>
<div class="ml-bench" role="list">
<div class="ml-row" role="listitem"><div class="ml-row-name">Grid epidemic<small>20,000 agents, 60 steps</small></div><div class="ml-bars"><div class="ml-bar ml-bar-mesa"><span>Mesa 2.3 10.86 s</span><b><i style="--w:100.00"></i></b></div><div class="ml-bar ml-bar-cells"><span>Modelly, cell lists 6.23 s</span><b><i style="--w:57.37"></i></b></div><div class="ml-bar ml-bar-mod"><span>Modelly, columns 0.22 s</span><b><i style="--w:2.03"></i></b></div></div><div class="ml-x" aria-label="50 times faster">50<small>x</small></div></div>
<div class="ml-row" role="listitem"><div class="ml-row-name">Predator-prey<small>~5,500 agents, 200 steps</small></div><div class="ml-bars"><div class="ml-bar ml-bar-mesa"><span>Mesa 2.3 5.79 s</span><b><i style="--w:100.00"></i></b></div><div class="ml-bar ml-bar-cells"><span>Modelly, cell lists 4.95 s</span><b><i style="--w:85.49"></i></b></div><div class="ml-bar ml-bar-mod"><span>Modelly, columns 0.78 s</span><b><i style="--w:13.47"></i></b></div></div><div class="ml-x" aria-label="7.4 times faster">7.4<small>x</small></div></div>
<div class="ml-row" role="listitem"><div class="ml-row-name">Flocking<small>4,000 agents, 50 steps</small></div><div class="ml-bars"><div class="ml-bar ml-bar-mesa"><span>Mesa 2.3 32.65 s</span><b><i style="--w:100.00"></i></b></div><div class="ml-bar ml-bar-mod"><span>Modelly, columns 1.05 s</span><b><i style="--w:3.22"></i></b></div></div><div class="ml-x" aria-label="31 times faster">31<small>x</small></div></div>
<div class="ml-row" role="listitem"><div class="ml-row-name">Virus on a network<small>30,000 agents, 100 steps</small></div><div class="ml-bars"><div class="ml-bar ml-bar-mesa"><span>Mesa 2.3 12.10 s</span><b><i style="--w:100.00"></i></b></div><div class="ml-bar ml-bar-mod"><span>Modelly, columns 0.30 s</span><b><i style="--w:2.48"></i></b></div></div><div class="ml-x" aria-label="40 times faster">40<small>x</small></div></div>
<div class="ml-row" role="listitem"><div class="ml-row-name">Insects, individuals<small>~26,000 agents, 120 days</small></div><div class="ml-bars"><div class="ml-bar ml-bar-mesa"><span>Mesa 2.3 5.55 s</span><b><i style="--w:100.00"></i></b></div><div class="ml-bar ml-bar-mod"><span>Modelly, columns 1.09 s</span><b><i style="--w:19.64"></i></b></div></div><div class="ml-x" aria-label="5.1 times faster">5.1<small>x</small></div></div>
<div class="ml-row" role="listitem"><div class="ml-row-name">Insects, cohorts<small>~26,000 agents, 120 days</small></div><div class="ml-bars"><div class="ml-bar ml-bar-mesa"><span>Mesa 2.3 5.55 s</span><b><i style="--w:100.00"></i></b></div><div class="ml-bar ml-bar-mod"><span>Modelly, columns 0.02 s</span><b><i style="--w:0.36"></i></b></div></div><div class="ml-x" aria-label="244 times faster">244<small>x</small></div></div>
</div>
<div class="ml-proof">
<p><strong>Same answers</strong>Every variant runs the same seeds. No summary statistic differs from Mesa's under Welch's t-test at p&nbsp;&lt;&nbsp;0.01.</p>
<p><strong>Same seed, same run</strong>The first seed runs twice per implementation and must reproduce exactly.</p>
<p><strong>Re-run it yourself</strong>The playbooks and the runner are in <a href="https://github.com/RemiPelloux/Modelly/tree/main/benchmarks/playbooks">benchmarks/playbooks</a>; the method is on the <a href="performance.html">performance page</a>.</p>
</div>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-uses-title">
<div class="ml-wrap">
<h2 id="ml-uses-title">What people model with it</h2>
<p class="ml-lede">Each sketch below is a small version of a playbook or a shipped example, running in your browser.</p>
<div class="ml-uses">
<article class="ml-use"><canvas data-sim="epidemic" role="img" aria-label="Animated sketch: Epidemics on a grid"></canvas><div><h3>Epidemics on a grid</h3><p>Susceptible, infected and recovered agents on a 20,000-cell torus. Exposure is one count over the grid's adjacency, so 60 steps take 0.22 s.</p><a href="performance.html">Read the playbook</a></div></article>
<article class="ml-use"><canvas data-sim="predator-prey" role="img" aria-label="Animated sketch: Predators, prey and grass"></canvas><div><h3>Predators, prey and grass</h3><p>Wolves and sheep are born and die every step while the grass grows back. Creating and removing agents costs what it costs in Mesa; walking and hunting are vectorised.</p><a href="examples/advanced/wolf_sheep.html">Open the Wolf-Sheep example</a></div></article>
<article class="ml-use"><canvas data-sim="flocking" role="img" aria-label="Animated sketch: Flocks in continuous space"></canvas><div><h3>Flocks in continuous space</h3><p>Boids align, gather and keep their distance through neighbour search in continuous space: 4,000 birds, 50 steps, about a second.</p><a href="examples/basic/boid_flockers.html">Open the Boids example</a></div></article>
<article class="ml-use"><canvas data-sim="network" role="img" aria-label="Animated sketch: Contagion on a network"></canvas><div><h3>Contagion on a network</h3><p>A virus moves along the edges of a 30,000-node random network. Recovered nodes can gain resistance or become susceptible again.</p><a href="examples/basic/virus_on_network.html">Open the network example</a></div></article>
<article class="ml-use"><canvas data-sim="insects" role="img" aria-label="Animated sketch: Pest control by sterile release"></canvas><div><h3>Pest control by sterile release</h3><p>A stage-structured insect population under sterile-male releases, the shaded bands. Grouping identical insects into cohorts keeps the law of the individual model and runs 120 days in 20 ms.</p><a href="vectorised_phases.html">See how cohorts stay exact</a></div></article>
<article class="ml-use"><canvas data-sim="schelling" role="img" aria-label="Animated sketch: Segregation from mild preferences"></canvas><div><h3>Segregation from mild preferences</h3><p>Schelling's model: agents who only want half their neighbours to match them still end up in sharply separated neighbourhoods.</p><a href="examples/basic/schelling.html">Open the Schelling example</a></div></article>
</div>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-code-title">
<div class="ml-wrap ml-code">
<div>
<h2 id="ml-code-title">A model in three pieces</h2>
<p class="ml-lede">Boltzmann's wealth model: agents wander a grid and hand a coin to whoever shares their cell.</p>
<ol>
<li><strong>A scenario</strong> holds the inputs: population, grid size, seed.</li>
<li><strong>Agents</strong> each know one thing: how to take their own step.</li>
<li><strong>A model</strong> owns the world and moves it forward in time.</li>
</ol>
</div>
<div>

```python
from modelly import Model
from modelly.discrete_space import CellAgent, OrthogonalMooreGrid
from modelly.experimental.scenarios import Scenario


class WealthScenario(Scenario):
    n: int = 120
    width: int = 12
    height: int = 12


class MoneyAgent(CellAgent):
    def __init__(self, model, cell):
        super().__init__(model)
        self.cell = cell
        self.wealth = 1

    def step(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        cellmates = [a for a in self.cell.agents if a is not self]
        if self.wealth > 0 and cellmates:
            self.random.choice(cellmates).wealth += 1
            self.wealth -= 1


class WealthModel(Model):
    def __init__(self, scenario: WealthScenario = WealthScenario):
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height), random=self.random
        )
        cells = self.random.choices(self.grid.all_cells.cells, k=scenario.n)
        MoneyAgent.create_agents(self, scenario.n, cells)

    def step(self):
        self.agents.shuffle_do("step")


model = WealthModel()
for _ in range(100):
    model.step()
```

</div>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-blocks-title">
<div class="ml-wrap">
<h2 id="ml-blocks-title">Everything a simulation study needs</h2>
<dl class="ml-blocks"><div><dt>Scenario</dt><dd>Parameters as a typed class: one run, one seed, one config object.</dd></div><div><dt>Agents</dt><dd>Classes with a step(), grouped in ordered AgentSets.</dd></div><div><dt>Columns</dt><dd>Attributes stored in numpy arrays, readable per agent and as a whole.</dd></div><div><dt>Space</dt><dd>Square and hexagonal grids, networks, Voronoi meshes, continuous space.</dd></div><div><dt>Time</dt><dd>Ticks, scheduled events, generators and priorities in one scheduler.</dd></div><div><dt>Data</dt><dd>Reporters and datasets that land in pandas, ready to plot.</dd></div><div><dt>Visualization</dt><dd>Browser dashboards with Solara, matplotlib and altair charts, notebooks.</dd></div><div><dt>Replications</dt><dd>Seeded parameter sweeps spread over processes.</dd></div></dl>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-next-title">
<div class="ml-wrap">
<h2 id="ml-next-title">Where to go next</h2>
<div class="ml-paths">
<a class="ml-path ml-path-lead" href="getting_started.html"><strong>Getting started</strong><span>The concepts, then twelve executable tutorials, from your first model to hybrid agent-based and discrete-event simulation.</span></a>
<a class="ml-path" href="using_modelly_in_your_project.html"><strong>Use Modelly in your project</strong><span>From an empty folder to a tested, replicated model.</span></a>
<a class="ml-path" href="examples.html"><strong>Examples</strong><span>Boltzmann wealth, Schelling, Game of Life, Sugarscape, Epstein civil violence and more.</span></a>
<a class="ml-path" href="migrating_from_mesa.html"><strong>Coming from Mesa</strong><span>A construct-by-construct map and the <code>python -m modelly.migrate</code> codemod.</span></a>
<a class="ml-path" href="apis/api_main.html"><strong>API reference</strong><span>Every class and function, documented from the source.</span></a>
</div>
</div>
</section>
<footer class="ml-foot">
<div class="ml-wrap ml-foot-grid">
<div>
<h2>Community and source</h2>
<ul>
<li><a href="https://github.com/RemiPelloux/Modelly">GitHub repository</a>: source, issues and pull requests.</li>
<li><a href="https://github.com/RemiPelloux/Modelly/discussions">Discussions</a>: questions and ideas.</li>
<li><a href="https://github.com/RemiPelloux/Modelly/blob/main/CHANGELOG.md">Changelog</a>: what each release added, changed and fixed.</li>
<li><a href="https://github.com/RemiPelloux/Modelly/blob/main/CONTRIBUTING.md">Contributing guide</a>: local setup, tests, lint and review.</li>
</ul>
</div>
<div>
<h2>Citing Modelly</h2>
<p>If Modelly contributes to a publication, cite it with the metadata in <a href="https://github.com/RemiPelloux/Modelly/blob/main/CITATION.cff">CITATION.cff</a>. GitHub's "Cite this repository" button formats it as APA or BibTeX. Modelly is licensed under <a href="https://github.com/RemiPelloux/Modelly/blob/main/LICENSE">Apache-2.0</a>.</p>
<p><a href="genindex.html">Index</a>, <a href="py-modindex.html">module index</a>, <a href="search.html">search</a>.</p>
</div>
</div>
</footer>
</div>

```{toctree}
:hidden: true
:maxdepth: 2

Getting started <getting_started>
Use Modelly in your project <using_modelly_in_your_project>
Examples <examples>
Migrating from Mesa <migrating_from_mesa>
Performance <performance>
Vectorised step phases <vectorised_phases>
Best practices <best-practices>
Overview <overview>
API reference <apis/api_main>
```

