"""Deprecated drawing arguments of SpaceRenderer: warn, then apply them.

Each function is called directly from the public SpaceRenderer method, so
``stacklevel=3`` reports the caller of that method.
"""

import warnings


def apply_deprecated_agent_args(renderer, agent_portrayal, kwargs):
    """Warn about and apply the arguments passed to draw_agents()."""
    if agent_portrayal is not None:
        warnings.warn(
            "Passing agent_portrayal to draw_agents() is deprecated and will be removed in a future release. "
            "Use setup_agents(agent_portrayal, **kwargs) before calling draw_agents().",
            FutureWarning,
            stacklevel=3,
        )
        renderer.agent_portrayal = agent_portrayal
    if kwargs:
        warnings.warn(
            "Passing kwargs to draw_agents() is deprecated. "
            "Use setup_agents(**kwargs) before calling draw_agents().",
            PendingDeprecationWarning,
            stacklevel=3,
        )
        renderer.draw_agent_kwargs.update(kwargs)


def apply_deprecated_render_args(
    renderer, agent_portrayal, property_layer_portrayal, kwargs
):
    """Warn about and apply the arguments passed to render()."""
    warnings.warn(
        "Passing parameters to render() is deprecated. "
        "Use setup_structure(), setup_agents(), and setup_property_layer() before calling render().",
        PendingDeprecationWarning,
        stacklevel=3,
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
        warnings.warn(
            "Passing kwargs to draw_structure() is deprecated. "
            "Use setup_structure(**kwargs) before calling draw_structure().",
            PendingDeprecationWarning,
            stacklevel=3,
        )
        renderer.draw_space_kwargs.update(kwargs)


def apply_deprecated_layer_portrayal(renderer, property_layer_portrayal):
    """Warn about and apply the portrayal passed to draw_property_layer()."""
    if property_layer_portrayal is not None:
        warnings.warn(
            "Passing property_layer_portrayal to draw_property_layer() is deprecated and will be removed in a future release. "
            "Use setup_property_layer(property_layer_portrayal) before calling draw_property_layer().",
            FutureWarning,
            stacklevel=3,
        )
        renderer.property_layer_portrayal = property_layer_portrayal
