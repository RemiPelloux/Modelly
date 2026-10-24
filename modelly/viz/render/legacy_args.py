"""Deprecated drawing arguments of SpaceRenderer: warn, then apply them.

Each function is called directly from the public SpaceRenderer method, so
``stacklevel=3`` reports the caller of that method.
"""

from modelly._deprecation import deprecated

STACKLEVEL = 3  # the caller of the public SpaceRenderer method


def apply_deprecated_agent_args(renderer, agent_portrayal, kwargs):
    """Warn about and apply the arguments passed to draw_agents()."""
    if agent_portrayal is not None:
        deprecated(
            "draw_agents(agent_portrayal)",
            "setup_agents(agent_portrayal) before draw_agents()",
            stacklevel=STACKLEVEL,
        )
        renderer.agent_portrayal = agent_portrayal
    if kwargs:
        deprecated(
            "draw_agents(**kwargs)",
            "setup_agents(**kwargs) before draw_agents()",
            stacklevel=STACKLEVEL,
        )
        renderer.draw_agent_kwargs.update(kwargs)


def apply_deprecated_render_args(
    renderer, agent_portrayal, property_layer_portrayal, kwargs
):
    """Warn about and apply the arguments passed to render()."""
    deprecated(
        "Passing parameters to render()",
        "setup_structure(), setup_agents() and setup_property_layer() before render()",
        stacklevel=STACKLEVEL,
    )
    if agent_portrayal is not None:
        renderer.agent_portrayal = agent_portrayal
    if property_layer_portrayal is not None:
        renderer.property_layer_portrayal = property_layer_portrayal

    deprecated_kwargs_map = {
        "space_kwargs": renderer.draw_space_kwargs,
        "agent_kwargs": renderer.draw_agent_kwargs,
    }
    for key, target_dict in deprecated_kwargs_map.items():
        if key in kwargs:
            value = kwargs.pop(key)
            if isinstance(value, dict):
                target_dict.update(value)

    # Update with any remaining kwargs (now that the dangerous ones are removed)
    renderer.draw_space_kwargs.update(kwargs)


def apply_deprecated_structure_args(renderer, kwargs):
    """Warn about and apply the kwargs passed to draw_structure()."""
    if kwargs:
        deprecated(
            "draw_structure(**kwargs)",
            "setup_structure(**kwargs) before draw_structure()",
            stacklevel=STACKLEVEL,
        )
        renderer.draw_space_kwargs.update(kwargs)


def apply_deprecated_layer_portrayal(renderer, property_layer_portrayal):
    """Warn about and apply the portrayal passed to draw_property_layer()."""
    if property_layer_portrayal is not None:
        deprecated(
            "draw_property_layer(property_layer_portrayal)",
            "setup_property_layer(property_layer_portrayal) before draw_property_layer()",
            stacklevel=STACKLEVEL,
        )
        renderer.property_layer_portrayal = property_layer_portrayal
