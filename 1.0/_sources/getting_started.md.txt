# Getting started
Modelly is a modular framework for building, analyzing and visualizing agent-based models.

**Agent-based models** are computer simulations involving multiple entities (the agents) acting and interacting with one another based on their programmed behavior. Agents can be used to represent living cells, animals, individual humans, even entire organizations or abstract entities. Sometimes, we may have an understanding of how the individual components of a system behave, and want to see what system-level behaviors and effects emerge from their interaction. Other times, we may have a good idea of how the system overall behaves, and want to figure out what individual behaviors explain it. Or we may want to see how to get agents to cooperate or compete most effectively. Or we may just want to build a cool toy with colorful little dots moving around.

## Overview
If you want to get a general idea of Modelly’s features and structure, start here:

- [Overview of the MODELLY library](overview): Learn about the core concepts and components of Modelly.

## Tutorials
If you want to learn how to build agent-based models step by step using Modelly, follow these tutorials:

- [Creating Your First Model](tutorials/0_first_model): Learn how to create your first Modelly model.
- [AgentSet](tutorials/1_agentset): Learn how to more effectively manage agents with Modelly's AgentSet.
- [Agent Activation](tutorials/2_agent_activation): Learn different ways to activate agents using `do`, `shuffle_do`, and `map` — covering random, sequential, simultaneous, staged, type-based, and conditional activation patterns.
- [Event Scheduling](tutorials/3_event_scheduling): Learn how to schedule events and manage time in your Modelly model.
- [Adding Space](tutorials/4_adding_space): Learn how to add space to your Modelly model and understand Modelly's space architecture.
- [Collecting Data](tutorials/5_collecting_data): Learn how to collect model level and agent level data with Modelly's DataCollector.
- [Basic Visualization](tutorials/6_visualization_basic): Learn how to build an interactive dashboard with Modelly's visualization module.
- [Dynamic Agent Visualization](tutorials/7_visualization_dynamic_agents): Learn how to dynamically represent your agents in your interactive dashboard.
- [Visualization using SpaceRenderer](tutorials/8_visualization_rendering_with_space_renderer): Learn how to use SpaceRenderer to its full extent to enhance your visualizations.
- [Property Layer Visualization](tutorials/9_visualization_property_layer_visualization): Learn how to visualize property layers in Modelly.
- [Custom Visualization Components](tutorials/10_visualization_custom): Learn how to add custom visual components to your interactive dashboard.
- [Discrete Event Simulation](tutorials/11_discrete_event_simulation): Learn how to build a pure event-driven model with `schedule_event` and validate it against queuing theory.
- [Hybrid ABM-DEVS Models](tutorials/12_hybrid_abm_devs): Learn how to combine `step()`-based agent activation with scheduled events in a spatial epidemic model.

## Examples
Modelly ships with a collection of example models. These are classic ABMs, so if you are familiar with ABMs and want to get a quick sense of how MODELLY works, these examples are great place to start. You can find them [here](examples).

## Further resources
To further explore Modelly and its features, we have the following resources available:

### Best practices
- [Modelly best practices](best-practices): an overview of tips and guidelines for using MODELLY.

### API documentation
- [Modelly API reference](apis/api_main.md): Detailed documentation of Modelly's classes and functions, one page per package (`modelly.core`, `modelly.space`, `modelly.time`, `modelly.data`, `modelly.behaviour`, `modelly.scenarios`, `modelly.batch`, `modelly.viz`).

### Source Code and development
- [Modelly GitHub repository](https://github.com/RemiPelloux/Modelly): Access the full source code of Modelly, contribute to its development, or report issues.
- [Modelly release notes](https://github.com/RemiPelloux/Modelly/releases): View the detailed changelog of Modelly, including all past releases and their features.

### Community and support
- [Modelly GitHub Discussions](https://github.com/RemiPelloux/Modelly/discussions): Join discussions, ask questions, and connect with other Modelly users.

Enjoy modelling with Modelly, and feel free to reach out!

### Coming from Mesa
- [Migrating from Mesa](migrating_from_mesa): a construct-by-construct map and a codemod, `python -m modelly.migrate`, that rewrites the mechanical parts and reports the rest.
