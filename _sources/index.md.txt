---
myst:
  html_meta:
    description: "Modelly is an open-source Python framework for agent-based modeling (ABM): agents in numpy columns, grids, networks and continuous space, seeded reproducible runs, calibration, a model hub, and 2.9 to 135 times the speed of Mesa 3.5."
    keywords: "agent-based modeling, agent-based model, ABM, Python, simulation, epidemic model, SIR, ecology, computational social science, Mesa alternative, NetLogo alternative, calibration, model hub"
---

# Modelly: agent-based modeling in Python

<div class="ml-landing">
<section class="ml-hero" data-hero aria-labelledby="ml-hero-title">
<canvas class="ml-hero-world" aria-hidden="true"></canvas>
<div class="ml-wrap ml-hero-in">
<div class="ml-hero-copy">
<p class="ml-hero-title" id="ml-hero-title" role="heading" aria-level="2">Agent-based models in Python, fast enough to explore.</p>
<p class="ml-hero-sub">Modelly is an open-source framework for agent-based modeling. Write agents with a <code>step()</code>, keep their state in numpy columns as the model grows, and get the same result from the same seed every time.</p>
<div class="ml-actions">
<a class="ml-btn ml-btn-primary" href="tutorials/0_first_model.html">Build your first model</a>
<button type="button" class="ml-pip" data-copy="pip install modelly-abm" aria-label="Copy the install command"><span>$</span><code title="pip install modelly-abm">pip install modelly-abm</code><em><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><rect x="5" y="5" width="9" height="9" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M11 3.5V3a1.5 1.5 0 0 0-1.5-1.5h-6A1.5 1.5 0 0 0 2 3v6a1.5 1.5 0 0 0 1.5 1.5H4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></em></button>
</div>
</div>
<div class="ml-deck" data-md="skip">
<p class="ml-deck-title">Running behind this page</p>
<div class="ml-tabs" role="group" aria-label="Model running behind this page">
<button type="button" data-pick="epidemic" aria-pressed="true">Epidemic</button><button type="button" data-pick="flocking" aria-pressed="false">Flocking</button><button type="button" data-pick="segregation" aria-pressed="false">Segregation</button>
</div>
<p class="ml-deck-how" data-out="how">Click or drag anywhere on the band to infect people.</p>
<pre class="ml-deck-code"><code data-out="code">class Person(CellAgent):
    def step(self):
        if self.state != SUSCEPTIBLE:
            return
        near = self.cell.neighborhood.agents
        sick = sum(a.state == INFECTED for a in near)
        risk = 1 - (1 - 0.12) ** sick
        if self.random.random() &lt; risk:
            self.state = INFECTED</code></pre>
<div class="ml-deck-ctl">
<label><span data-out="label">Transmission</span> <input type="range" min="0.04" max="0.4" step="0.01" value="0.12" data-param> <b data-out="value">0.12</b></label>
</div>
<p class="ml-deck-stats"><span><b data-out="agents">0</b> agents</span><span>step <b data-out="step">0</b></span><a data-out="source" href="zoo/index.html">The full example</a><button type="button" class="ml-btn ml-btn-ghost ml-btn-small" data-toggle>Pause</button></p>
</div>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-bench-title">
<div class="ml-wrap">
<h2 id="ml-bench-title">The same models, 2.9 to 135 times faster than Mesa 3.5</h2>
<p class="ml-lede">Nine playbooks written in the idiom of Mesa 3.5 and of Modelly: median CPU seconds over ten rounds, one fresh interpreter per run, on one pinned core. The scale is logarithmic.</p>
<div class="ml-dots" aria-hidden="true">
<div class="ml-dots-axis" aria-hidden="true"><span></span><span class="ml-axis"><i style="--x:0">0.01 s</i><i style="--x:33.3">0.1 s</i><i style="--x:66.7">1 s</i><i style="--x:100">10 s</i></span><span>faster</span></div>
<div class="ml-dot-row"><span><strong>Grid epidemic</strong><small>20,000 agents, 60 steps</small></span><span class="ml-track" style="--a:40.14;--b:86.7;--k:0"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:0">26&times;</span></div>
<div class="ml-dot-row"><span><strong>Predator-prey</strong><small>~5,400 agents, 200 steps</small></span><span class="ml-track" style="--a:57.2;--b:85.49;--k:1"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:1">7.1&times;</span></div>
<div class="ml-dot-row"><span><strong>Flocking</strong><small>4,000 agents, 50 steps</small></span><span class="ml-track" style="--a:62.5;--b:100;--k:2"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:2">33&times;</span></div>
<div class="ml-dot-row"><span><strong>Virus on a network</strong><small>30,000 agents, 100 steps</small></span><span class="ml-track" style="--a:42.63;--b:80.05;--k:3"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:3">13&times;</span></div>
<div class="ml-dot-row"><span><strong>Insects, individuals</strong><small>~26,000 agents, 120 days</small></span><span class="ml-track" style="--a:61.5;--b:76.7;--k:4"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:4">2.9&times;</span></div>
<div class="ml-dot-row"><span><strong>Insects, cohorts</strong><small>~26,000 agents, 120 days</small></span><span class="ml-track" style="--a:5.68;--b:76.7;--k:5"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:5">135&times;</span></div>
<div class="ml-dot-row"><span><strong>Schelling segregation</strong><small>~32,000 residents, 40 steps</small></span><span class="ml-track" style="--a:43.37;--b:85.09;--k:6"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:6">18&times;</span></div>
<div class="ml-dot-row"><span><strong>Boltzmann wealth</strong><small>10,000 agents, 100 steps</small></span><span class="ml-track" style="--a:50.62;--b:68.56;--k:7"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:7">3.5&times;</span></div>
<div class="ml-dot-row"><span><strong>Sugarscape</strong><small>1,600 foragers, 100 steps</small></span><span class="ml-track" style="--a:50.62;--b:71.95;--k:8"><i class="ml-span"></i><b class="ml-pt-mesa"></b><b class="ml-pt-mod"></b></span><span class="ml-speed" style="--k:8">4.4&times;</span></div>
</div>
<div class="ml-sr-only">
<table>
<caption>Seconds per run, median of ten rounds</caption>
<thead><tr><th scope="col">Model</th><th scope="col">Size</th><th scope="col">Mesa 3.5</th><th scope="col">Modelly</th><th scope="col">Speed-up</th></tr></thead>
<tbody>
<tr><th scope="row">Grid epidemic</th><td>20,000 agents, 60 steps</td><td>3.99 s</td><td>0.16 s</td><td>26&times;</td></tr>
<tr><th scope="row">Predator-prey</th><td>~5,400 agents, 200 steps</td><td>3.67 s</td><td>0.52 s</td><td>7.1&times;</td></tr>
<tr><th scope="row">Flocking</th><td>4,000 agents, 50 steps</td><td>24.49 s</td><td>0.75 s</td><td>33&times;</td></tr>
<tr><th scope="row">Virus on a network</th><td>30,000 agents, 100 steps</td><td>2.52 s</td><td>0.19 s</td><td>13&times;</td></tr>
<tr><th scope="row">Insects, individuals</th><td>~26,000 agents, 120 days</td><td>2 s</td><td>0.7 s</td><td>2.9&times;</td></tr>
<tr><th scope="row">Insects, cohorts</th><td>~26,000 agents, 120 days</td><td>2 s</td><td>0.015 s</td><td>135&times;</td></tr>
<tr><th scope="row">Schelling segregation</th><td>~32,000 residents, 40 steps</td><td>3.57 s</td><td>0.2 s</td><td>18&times;</td></tr>
<tr><th scope="row">Boltzmann wealth</th><td>10,000 agents, 100 steps</td><td>1.14 s</td><td>0.33 s</td><td>3.5&times;</td></tr>
<tr><th scope="row">Sugarscape</th><td>1,600 foragers, 100 steps</td><td>1.44 s</td><td>0.33 s</td><td>4.4&times;</td></tr>
</tbody>
</table>
</div>
<p class="ml-dots-key" aria-hidden="true"><span class="ml-key-mesa">Mesa 3.5</span> <span class="ml-key-mod">Modelly</span></p>
<div class="ml-proof">
<p><strong>Same answers</strong> Every variant runs the same seeds. Over 100 paired seeds, no summary statistic differs from Mesa's after a Holm correction.</p>
<p><strong>Same seed, same run</strong> Each implementation runs its first seed twice and must reproduce it exactly.</p>
<p><strong>Re-run it yourself</strong> The playbooks and the runner are in <a href="https://github.com/RemiPelloux/Modelly/tree/main/benchmarks/playbooks">benchmarks/playbooks</a>; the method, the other baselines (Mesa 2.3, mesa-frames, hand-vectorised Mesa) and the variance are on the <a href="performance.html">performance page</a>.</p>
</div>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-uses-title">
<div class="ml-wrap">
<h2 id="ml-uses-title">What people model with it</h2>
<p class="ml-lede">Each sketch below is a small version of a playbook or a shipped example, running in your browser.</p>
<div class="ml-uses">
<article class="ml-use"><canvas data-sim="epidemic" role="img" aria-label="Animated sketch: Epidemics on a grid"></canvas><div><h3>Epidemics on a grid</h3><p>Susceptible, infected and recovered agents on a 20,000-cell torus. Exposure is one count over the grid's adjacency, so 60 steps take 0.32 s, building included.</p><a href="performance.html">Read the playbook</a></div></article>
<article class="ml-use"><canvas data-sim="predator-prey" role="img" aria-label="Animated sketch: Predators, prey and grass"></canvas><div><h3>Predators, prey and grass</h3><p>Wolves and sheep are born and die every step while the grass grows back. Creating and removing agents costs what it costs in Mesa; walking and hunting are vectorised.</p><a href="examples/advanced/wolf_sheep.html">Open the Wolf-Sheep example</a></div></article>
<article class="ml-use"><canvas data-sim="flocking" role="img" aria-label="Animated sketch: Flocks in continuous space"></canvas><div><h3>Flocks in continuous space</h3><p>Boids align, gather and keep their distance through neighbour search in continuous space: 4,000 birds, 50 steps, about a second.</p><a href="examples/basic/boid_flockers.html">Open the Boids example</a></div></article>
<article class="ml-use"><canvas data-sim="network" role="img" aria-label="Animated sketch: Contagion on a network"></canvas><div><h3>Contagion on a network</h3><p>A virus moves along the edges of a 30,000-node random network. Recovered nodes can gain resistance or become susceptible again.</p><a href="examples/basic/virus_on_network.html">Open the network example</a></div></article>
<article class="ml-use"><canvas data-sim="insects" role="img" aria-label="Animated sketch: Pest control by sterile release"></canvas><div><h3>Pest control by sterile release</h3><p>A stage-structured insect population under sterile-male releases, the shaded bands. Grouping identical insects into cohorts keeps the law of the individual model and runs 120 days in 13 ms.</p><a href="vectorised_phases.html">See how cohorts stay exact</a></div></article>
<article class="ml-use"><canvas data-sim="schelling" role="img" aria-label="Animated sketch: Segregation from mild preferences"></canvas><div><h3>Segregation from mild preferences</h3><p>Schelling's model: agents who only want half their neighbours to match them still end up in sharply separated neighbourhoods.</p><a href="examples/basic/schelling.html">Open the Schelling example</a></div></article>
</div>
</div>
</section>
<section class="ml-section" aria-labelledby="ml-paths-title">
<div class="ml-wrap">
<h2 id="ml-paths-title">Start from what you need</h2>
<form class="ml-finder" role="search" action="search.html" method="get" autocomplete="off">
<label for="ml-find">What do you want to do?</label>
<input id="ml-find" name="q" type="search" placeholder="for example: calibrate, GPU, from R" aria-describedby="ml-find-help" aria-controls="ml-find-results">
<p id="ml-find-help" class="ml-find-help">Type a task; the matching guides appear below. Enter searches the whole documentation.</p>
<ul id="ml-find-results" class="ml-find-results" aria-live="polite"></ul>
</form>
<div class="ml-paths-grid">
<nav aria-labelledby="ml-p1"><h3 id="ml-p1">Build a model</h3><ul>
<li><a href="getting_started.html">Getting started</a>, then twelve tutorials</li>
<li><a href="zoo/index.html">The model zoo</a>: 18 validated models to start from</li>
<li><a href="performance.html">Columns and cohorts</a> for large populations</li>
<li><a href="agent_odes.html">ODEs inside agents</a>, with events and delays</li>
<li><a href="geospatial.html">Real maps</a> and <a href="networks.html">networks</a></li>
<li><a href="migrating_from_mesa.html">Coming from Mesa</a> or <a href="netlogo.html">NetLogo</a></li>
</ul></nav>
<nav aria-labelledby="ml-p2"><h3 id="ml-p2">Run a study</h3><ul>
<li><a href="experiments.html">Sweeps and replications</a>, on a laptop or a cluster</li>
<li><a href="calibration.html">Calibrate</a> to data, with posteriors</li>
<li><a href="sensitivity.html">Sensitivity analysis</a> and <a href="emulators.html">emulators</a></li>
<li><a href="decide.html">Compare strategies</a> with intervals and costs</li>
<li><a href="explain.html">Causes</a>: effects, attribution, counterfactuals</li>
</ul></nav>
<nav aria-labelledby="ml-p3"><h3 id="ml-p3">Trust and share it</h3><ul>
<li><a href="provenance.html">Reproducible studies</a> a reviewer reruns</li>
<li><a href="model_cards.html">Model cards</a> checked against the code</li>
<li><a href="hub.html">The model hub</a>: publish, install, cite</li>
<li><a href="lint.html">Checking a model</a> for reproducibility bugs</li>
</ul></nav>
<nav aria-labelledby="ml-p4"><h3 id="ml-p4">Work your way</h3><ul>
<li><a href="studio.html">Studio</a> in the browser, with no code</li>
<li><a href="r_and_julia.html">From R and Julia</a></li>
<li><a href="browser.html">A model as a web page</a></li>
<li><a href="windows_no_admin.html">Windows without admin rights</a></li>
<li><a href="accessibility.html">Five languages</a>, WCAG 2.2 AA</li>
</ul></nav>
<nav aria-labelledby="ml-p5"><h3 id="ml-p5">Teach with it</h3><ul>
<li><a href="course/index.html">A twelve-session course</a></li>
<li><a href="course/instructors.html">Instructor notes</a> and assessments</li>
<li><a href="course/from_netlogo.html">Moving a NetLogo course</a></li>
<li><a href="studio.html#studio-for-everyone">Classroom mode</a> in Studio</li>
</ul></nav>
</div>
</div>
</section>
<section class="ml-section ml-new" aria-labelledby="ml-new-title">
<div class="ml-wrap ml-new-grid">
<div>
<h2 id="ml-new-title">New in 1.5</h2>
<p class="ml-lede">Ecosystem and collaboration: everything a colleague, a policy team or a class needs to reuse a model. <a href="whats_new.html">What's new</a> has every release.</p>
</div>
<dl>
<div><dt><a href="hub.html">A model hub</a></dt><dd><code>modelly hub install within_host</code>, with cards, DOIs and checksums.</dd></div>
<div><dt><a href="decide.html">Decisions</a></dt><dd>Strategies on the same chance events, ranked with intervals and costs.</dd></div>
<div><dt><a href="agent_odes.html">Dynamics in agents</a></dt><dd>An ODE, a delay or a stochastic equation in every agent, solved as one batch.</dd></div>
<div><dt><a href="llm_agents.html">Agents that remember</a></dt><dd>Language-model agents with memory, plans, tools and conversations, replayed offline.</dd></div>
<div><dt><a href="r_and_julia.html">R and Julia</a></dt><dd><code>library(modelly)</code> and <code>using Modelly</code>, tested on three systems.</dd></div>
<div><dt><a href="deprecations.html">Ready for 2.0</a></dt><dd><code>modelly migrate --check-2.0</code> lists what a project must change.</dd></div>
</dl>
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
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.scenarios import Scenario


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
<section class="ml-section" aria-labelledby="ml-ai-title">
<div class="ml-wrap ml-ai">
<div>
<h2 id="ml-ai-title">Reading the docs with an AI assistant</h2>
<p class="ml-lede">Every page is also plain Markdown. Paste one into a chat with the <em>Copy page</em> button at its top, or point your assistant at the whole documentation in one file.</p>
</div>
<ul class="ml-ai-links">
<li><a href="llms.txt"><code>llms.txt</code></a> the index of every page, with a line on each</li>
<li><a href="llms-full.txt"><code>llms-full.txt</code></a> the whole documentation as one Markdown file</li>
<li><a href="getting_started.md"><code>getting_started.md</code></a> any page: replace <code>.html</code> with <code>.md</code></li>
</ul>
</div>
</section>
<footer class="ml-foot">
<div class="ml-wrap ml-foot-grid">
<div>
<h2>Community and source</h2>
<ul>
<li><a href="https://github.com/RemiPelloux/Modelly">GitHub repository</a>: source, issues and pull requests.</li>
<li><a href="https://github.com/RemiPelloux/Modelly/discussions">Discussions</a>: questions and ideas.</li>
<li><a href="whats_new.html">What's new</a>: what each release lets you do, feature by feature.</li>
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

Get started <getting_started>
Other languages <translations/index>
Examples <models>
Guides <guides>
Performance <scale>
API <apis/api_main>
Releases <releases>
```

