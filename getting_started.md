# Getting started

Also in [Français](https://remipelloux.github.io/Modelly/translations/fr/getting_started.html), [Español](https://remipelloux.github.io/Modelly/translations/es/getting_started.html), [Português](https://remipelloux.github.io/Modelly/translations/pt/getting_started.html) and [中文](https://remipelloux.github.io/Modelly/translations/zh/getting_started.html).

Modelly is a modular framework for building, analyzing and visualizing agent-based models.

**Agent-based models** are computer simulations involving multiple entities (the agents) acting and interacting with one another based on their programmed behavior. Agents can be used to represent living cells, animals, individual humans, even entire organizations or abstract entities. Sometimes, we may have an understanding of how the individual components of a system behave, and want to see what system-level behaviors and effects emerge from their interaction. Other times, we may have a good idea of how the system overall behaves, and want to figure out what individual behaviors explain it. Or we may want to see how to get agents to cooperate or compete most effectively. Or we may just want to build a cool toy with colorful little dots moving around.

## Overview

If you want to get a general idea of Modelly’s features and structure, start here:

- [Overview of the MODELLY library](https://remipelloux.github.io/Modelly/overview.html): Learn about the core concepts and components of Modelly.

## Tutorials

If you want to learn how to build agent-based models step by step using Modelly, follow these tutorials:

- [Creating Your First Model](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html): Learn how to create your first Modelly model.
- [AgentSet](https://remipelloux.github.io/Modelly/tutorials/1_agentset.html): Learn how to more effectively manage agents with Modelly’s AgentSet.
- [Agent Activation](https://remipelloux.github.io/Modelly/tutorials/2_agent_activation.html): Learn different ways to activate agents using `do`, `shuffle_do`, and `map` — covering random, sequential, simultaneous, staged, type-based, and conditional activation patterns.
- [Event Scheduling](https://remipelloux.github.io/Modelly/tutorials/3_event_scheduling.html): Learn how to schedule events and manage time in your Modelly model.
- [Adding Space](https://remipelloux.github.io/Modelly/tutorials/4_adding_space.html): Learn how to add space to your Modelly model and understand Modelly’s space architecture.
- [Collecting Data](https://remipelloux.github.io/Modelly/tutorials/5_collecting_data.html): Learn how to collect model level and agent level data with Modelly’s DataCollector.
- [Basic Visualization](https://remipelloux.github.io/Modelly/tutorials/6_visualization_basic.html): Learn how to build an interactive dashboard with Modelly’s visualization module.
- [Dynamic Agent Visualization](https://remipelloux.github.io/Modelly/tutorials/7_visualization_dynamic_agents.html): Learn how to dynamically represent your agents in your interactive dashboard.
- [Visualization using SpaceRenderer](https://remipelloux.github.io/Modelly/tutorials/8_visualization_rendering_with_space_renderer.html): Learn how to use SpaceRenderer to its full extent to enhance your visualizations.
- [Property Layer Visualization](https://remipelloux.github.io/Modelly/tutorials/9_visualization_property_layer_visualization.html): Learn how to visualize property layers in Modelly.
- [Custom Visualization Components](https://remipelloux.github.io/Modelly/tutorials/10_visualization_custom.html): Learn how to add custom visual components to your interactive dashboard.
- [Discrete Event Simulation](https://remipelloux.github.io/Modelly/tutorials/11_discrete_event_simulation.html): Learn how to build a pure event-driven model with `schedule_event` and validate it against queuing theory.
- [Hybrid ABM-DEVS Models](https://remipelloux.github.io/Modelly/tutorials/12_hybrid_abm_devs.html): Learn how to combine `step()`-based agent activation with scheduled events in a spatial epidemic model.

## Your own project

- [Using Modelly in your project](https://remipelloux.github.io/Modelly/using_modelly_in_your_project.html): from an empty folder to a reproducible, measured model that lives in its own repository.
- [Starting a project](https://remipelloux.github.io/Modelly/new_project.html): `modelly new` writes a project that is seeded, tested and linted from its first commit.
- [Modelly best practices](https://remipelloux.github.io/Modelly/best-practices.html): an overview of tips and guidelines for using Modelly.

## Courses and domain tutorials

- [Course](https://remipelloux.github.io/Modelly/course/index.html): twelve sessions that take a class from a first model to a validated, reproducible study of its own.
- [Domain tutorials](https://remipelloux.github.io/Modelly/tutorials/domains/index.html): one tutorial per field, each built on a model of the zoo.

## Coming from another tool

- [Migrating from Mesa](https://remipelloux.github.io/Modelly/migrating_from_mesa.html): a construct-by-construct map and a codemod, `python -m modelly.migrate`, that rewrites the mechanical parts and reports the rest.
- [From NetLogo](https://remipelloux.github.io/Modelly/netlogo.html): `python -m modelly.netlogo` translates a `.nlogo` model into a Python module you can run, test and lint.
- [From R and Julia](https://remipelloux.github.io/Modelly/r_and_julia.html): read Modelly’s Parquet results from R and Julia, and drive a model from R.

## Examples

Modelly ships with a collection of example models. These are classic ABMs, so if you are familiar with ABMs and want to get a quick sense of how MODELLY works, these examples are great place to start. You can find them [here](https://remipelloux.github.io/Modelly/examples.html).

## Further resources

To further explore Modelly and its features, we have the following resources available:

### API documentation

- [Modelly API reference](https://remipelloux.github.io/Modelly/apis/api_main.html): Detailed documentation of Modelly’s classes and functions, one page per package (`modelly.core`, `modelly.space`, `modelly.time`, `modelly.data`, `modelly.behaviour`, `modelly.scenarios`, `modelly.batch`, `modelly.viz`).

### Source Code and development

- [Modelly GitHub repository](https://github.com/RemiPelloux/Modelly): Access the full source code of Modelly, contribute to its development, or report issues.
- [Modelly release notes](https://github.com/RemiPelloux/Modelly/releases): View the detailed changelog of Modelly, including all past releases and their features.

### Community and support

- [Modelly GitHub Discussions](https://github.com/RemiPelloux/Modelly/discussions): Join discussions, ask questions, and connect with other Modelly users.

Enjoy modelling with Modelly, and feel free to reach out!
