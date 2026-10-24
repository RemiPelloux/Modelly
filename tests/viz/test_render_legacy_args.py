"""Tests for the deprecated drawing arguments SpaceRenderer still accepts."""

import warnings
from types import SimpleNamespace

import pytest

from modelly.viz.render.legacy_args import (
    apply_deprecated_agent_args,
    apply_deprecated_layer_portrayal,
    apply_deprecated_render_args,
    apply_deprecated_structure_args,
)


def _renderer():
    return SimpleNamespace(
        agent_portrayal=None,
        property_layer_portrayal=None,
        draw_agent_kwargs={},
        draw_space_kwargs={},
    )


def _portray(agent):
    return {}


def test_agent_args_none_is_silent():
    """Agent args none is silent."""
    renderer = _renderer()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        apply_deprecated_agent_args(renderer, None, {})
    assert renderer.agent_portrayal is None
    assert renderer.draw_agent_kwargs == {}


def test_agent_args_portrayal_and_kwargs_warn_and_apply():
    """Agent args portrayal and kwargs warn and apply."""
    renderer = _renderer()
    with (
        pytest.warns(FutureWarning, match=r"draw_agents\(agent_portrayal\)"),
        pytest.warns(DeprecationWarning, match=r"draw_agents\(\*\*kwargs\)"),
    ):
        apply_deprecated_agent_args(renderer, _portray, {"s": 4})
    assert renderer.agent_portrayal is _portray
    assert renderer.draw_agent_kwargs == {"s": 4}


def test_render_args_route_space_and_agent_kwargs():
    """Render args route space and agent kwargs."""
    renderer = _renderer()
    layers = {"sugar": {"colormap": "viridis"}}
    kwargs = {
        "space_kwargs": {"color": "grey"},
        "agent_kwargs": {"alpha": 0.5},
        "linewidth": 2,
    }
    with pytest.warns(DeprecationWarning, match="parameters to render"):
        apply_deprecated_render_args(renderer, _portray, layers, kwargs)
    assert renderer.agent_portrayal is _portray
    assert renderer.property_layer_portrayal is layers
    assert renderer.draw_agent_kwargs == {"alpha": 0.5}
    assert renderer.draw_space_kwargs == {"color": "grey", "linewidth": 2}
    assert "space_kwargs" not in kwargs
    assert "agent_kwargs" not in kwargs


def test_render_args_ignore_non_dict_kwargs_and_keep_portrayals():
    """Render args ignore non dict kwargs and keep portrayals."""
    renderer = _renderer()
    renderer.agent_portrayal = _portray
    with pytest.warns(DeprecationWarning):
        apply_deprecated_render_args(
            renderer, None, None, {"space_kwargs": "bogus", "agent_kwargs": None}
        )
    assert renderer.agent_portrayal is _portray
    assert renderer.property_layer_portrayal is None
    assert renderer.draw_space_kwargs == {}
    assert renderer.draw_agent_kwargs == {}


def test_structure_args():
    """Structure args."""
    renderer = _renderer()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        apply_deprecated_structure_args(renderer, {})
    with pytest.warns(DeprecationWarning, match="draw_structure"):
        apply_deprecated_structure_args(renderer, {"color": "red"})
    assert renderer.draw_space_kwargs == {"color": "red"}


def test_layer_portrayal():
    """Layer portrayal."""
    renderer = _renderer()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        apply_deprecated_layer_portrayal(renderer, None)
    assert renderer.property_layer_portrayal is None
    portrayal = {"sugar": {"color": "red"}}
    with pytest.warns(FutureWarning, match="draw_property_layer"):
        apply_deprecated_layer_portrayal(renderer, portrayal)
    assert renderer.property_layer_portrayal is portrayal


def test_warnings_point_at_the_renderer_caller():
    """stacklevel=3 attributes the warning to whoever called the public method."""

    def public_method(renderer):
        apply_deprecated_structure_args(renderer, {"color": "red"})

    with pytest.warns(DeprecationWarning) as record:
        public_method(_renderer())
    assert record[0].filename == __file__
