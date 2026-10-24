"""Paged, draggable grid layout of SolaraViz components."""

from __future__ import annotations

import collections
from collections.abc import Callable
from typing import TYPE_CHECKING

import reacton.core
import solara

from modelly.viz.utils import update_counter

if TYPE_CHECKING:
    from modelly.core.model import Model

_GRID_COLUMNS = 2
_ITEM_WIDTH = 6
_ITEM_HEIGHT = 10
_ROW_SPACING = 16


def _wrap_component(
    component: reacton.core.Component | Callable[[Model], reacton.core.Component],
) -> reacton.core.Component:
    """Wrap a component in an auto-updated Solara component if needed."""
    if isinstance(component, reacton.core.Component):
        return component

    @solara.component
    def WrappedComponent(model):
        update_counter.get()
        return component(model)

    return WrappedComponent


def _build_pages(components: list) -> tuple[dict, list]:
    """Group the components by page and return ``(pages, sorted page indices)``."""
    # Backward's compatibility, page = 0 if not passed.
    for i, comp in enumerate(components):
        if not isinstance(comp, tuple):
            components[i] = (comp, 0)

    # Build pages mapping
    pages = collections.defaultdict(list)
    for component, page_index in components:
        pages[page_index].append(_wrap_component(component))

    # Fill in missing page indices for sequential tab order
    all_indices = sorted(pages.keys())
    if len(all_indices) > 1:
        min_page, max_page = all_indices[0], all_indices[-1]
        all_indices = list(range(min_page, max_page + 1))
        for idx in all_indices:
            pages.setdefault(idx, [])

    return pages, all_indices


def _sync_layouts(components, pages, layouts, set_layouts) -> None:
    """Keep the per-page grid layouts in sync with the pages."""
    if not components:  # Handle empty case inside the effect
        return

    current_keys = set(pages.keys())
    layout_keys = set(layouts.keys())

    # Add layouts for new pages
    new_layouts = {
        index: make_initial_grid_layout(len(pages[index]))
        for index in current_keys - layout_keys
    }

    # Remove layouts for deleted pages
    cleaned_layouts = {k: v for k, v in layouts.items() if k in current_keys}

    if new_layouts or len(cleaned_layouts) != len(layouts):
        set_layouts({**cleaned_layouts, **new_layouts})


def _layout_change_handler(set_layouts, page_id):
    """Return a callback that stores a new grid layout for ``page_id``."""

    def on_layout_change(new_layout, current_page_id=page_id):
        set_layouts(lambda old: {**old, current_page_id: new_layout})

    return on_layout_change


def _render_page(model, page_components, page_layout, on_layout_change) -> None:
    """Render one page's components in a draggable, resizable grid."""
    if not page_layout:
        return
    solara.GridDraggable(
        items=[c(model) for c in page_components],
        grid_layout=page_layout,
        resizable=True,
        draggable=True,
        on_grid_layout=on_layout_change,
    )


def _render_tabs(page_indices, current_tab_index, set_current_tab_index) -> None:
    """Render the tab navigation bar, one tab per page."""
    with solara.v.Tabs(v_model=current_tab_index, on_v_model=set_current_tab_index):
        for index in page_indices:
            solara.v.Tab(children=[f"Page {index}"])


@solara.component
def ComponentsView(
    components: list[tuple[reacton.core.Component], int]
    | list[tuple[Callable[[Model], reacton.core.Component], int]],
    model: Model,
):
    """Display a list of components.

    Args:
        components: List of (components, page) to display
        model: Model instance to pass to each component
    """
    current_tab_index, set_current_tab_index = solara.use_state(0)
    layouts, set_layouts = solara.use_state({})

    pages, sorted_page_indices = _build_pages(components)
    solara.use_effect(
        lambda: _sync_layouts(components, pages, layouts, set_layouts),
        list(pages.keys()),
    )

    # Allow early return (which is now safe because all hooks have been called)
    if not components:
        return

    _render_tabs(sorted_page_indices, current_tab_index, set_current_tab_index)

    with solara.v.Window(v_model=current_tab_index):
        for i, page_id in enumerate(sorted_page_indices):
            with solara.v.WindowItem():
                # Use tab index 'i' instead of 'page_id' because solara.v.Window
                # Tracks active tabs using 0-based indexing, which may differ from page IDs.
                if i == current_tab_index:
                    handler = _layout_change_handler(set_layouts, page_id)
                    _render_page(model, pages[page_id], layouts.get(page_id), handler)


def make_initial_grid_layout(num_components):
    """Create an initial grid layout for visualization components.

    Args:
        num_components: Number of components to display

    Returns:
        list: Initial grid layout configuration
    """
    return [
        {
            "i": i,
            "w": _ITEM_WIDTH,
            "h": _ITEM_HEIGHT,
            "moved": False,
            "x": _ITEM_WIDTH * (i % _GRID_COLUMNS),
            "y": _ROW_SPACING * (i - i % _GRID_COLUMNS),
        }
        for i in range(num_components)
    ]
