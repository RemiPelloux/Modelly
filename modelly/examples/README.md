# Modelly Core Examples
This repository contains a curated set of classic agent-based models implemented using Modelly. These core examples are maintained by the Modelly development team and serve as both demonstrations of Modelly's capabilities and starting points for your own models.

## Overview
The examples are categorized into three groups:
1. **Basic Examples** - Simpler models that use only stable Modelly features; ideal for beginners
2. **Advanced Examples** - More complex models that demonstrate additional concepts
3. **Behaviour Examples** - Models built on the behaviour building blocks (`modelly.behaviour`): meta-agents and continuous states

## Basic Examples
The basic examples are relatively simple and use only the core building blocks: agents, spaces, scenarios, data collection and the browser visualization. They are good starting points for learning how to use Modelly.

### [Boltzmann Wealth Model](basic/boltzmann_wealth_model)
Completed code to go along with the [tutorial](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html) on making a simple model of how a highly-skewed wealth distribution can emerge from simple rules.

### [Boids Flockers Model](basic/boid_flockers)
[Boids](https://en.wikipedia.org/wiki/Boids)-style flocking model, demonstrating the use of agents moving through a continuous space following direction vectors.

### [Conway's Game of Life](basic/conways_game_of_life)
Implementation of [Conway's Game of Life](https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life), a cellular automata where simple rules can give rise to complex patterns.

### [Schelling Segregation Model](basic/schelling)
Modelly implementation of the classic [Schelling segregation](http://nifty.stanford.edu/2014/mccown-schelling-model-segregation/) model.

### [Virus on a Network Model](basic/virus_on_network)
This model is based on the NetLogo [Virus on a Network](https://ccl.northwestern.edu/netlogo/models/VirusonaNetwork) model.

## Advanced Examples
The advanced examples are more complex. They are good starting points for learning how to build more complex models.

### [Epstein Civil Violence Model](advanced/epstein_civil_violence)
Joshua Epstein's [model](https://www.pnas.org/doi/10.1073/pnas.092080199) of how a decentralized uprising can be suppressed or reach a critical mass of support.

### [Demographic Prisoner's Dilemma on a Grid](advanced/pd_grid)
Grid-based demographic prisoner's dilemma model, demonstrating how simple rules can lead to the emergence of widespread cooperation -- and how a model activation regime can change its outcome.

### [Sugarscape Model with Traders](advanced/sugarscape_g1mt)
This is Epstein & Axtell's Sugarscape model with Traders, a detailed description is in
<!-- vale Google.WordList = NO -->
Chapter four of *Growing Artificial Societies: Social Science from the Bottom Up (1996)*.
<!-- vale Google.WordList = YES -->
The model shows how emergent price equilibrium can happen via decentralized dynamics.

### [Wolf-Sheep Predation Model](advanced/wolf_sheep)
Implementation of an ecological model of predation and reproduction, based on the NetLogo [Wolf Sheep Predation](http://ccl.northwestern.edu/netlogo/models/WolfSheepPredation) model.

## Behaviour Examples
These examples use `modelly.behaviour` (meta-agents, continuous states and thresholds) and `modelly.time.signals`. Those packages follow semantic versioning like the rest of Modelly; the tram model still lives in the `experimental/` example folder.

### [Alliance Formation Model](advanced/alliance_formation)
Demonstrates `modelly.behaviour.meta_agents`: agents form alliances through a game-theoretic process, and the resulting alliances become meta-agents that can themselves form higher-level alliances.

### [Tram Route Model](behaviour/tram_model)
Demonstrates continuous states and thresholds: a tram accelerates, coasts, brakes and dwells its way along a route, with every transition solved for analytically and scheduled on the event queue rather than polled for on each tick.
