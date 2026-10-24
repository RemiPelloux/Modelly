"""Third-party extensions found through package entry points.

A package extends Modelly by declaring entry points in one of the groups of ``GROUPS``,
for example in its ``pyproject.toml``::

    [project.entry-points."modelly.spaces"]
    hexworld = "hexworld.space:HexWorld"

``discover(group)`` lists what is installed without importing anything; each ``Plugin`` is
imported the first time it is loaded. A plugin that fails to import raises
``PluginError`` naming the plugin and its distribution, and never stops the others from
being found or loaded: ``load_all`` returns the loaded objects and the errors apart.

    from modelly.plugins import discover

    spaces = discover("modelly.spaces")  # {"hexworld": Plugin(...)}
    HexWorld = spaces["hexworld"].load()
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from typing import Any

GROUPS = (
    "modelly.spaces",
    "modelly.executors",
    "modelly.samplers",
    "modelly.collectors",
    "modelly.studio_views",
    "modelly.lint_rules",
)


# Marks a plugin not imported yet (a plugin may legitimately load as None).
_UNLOADED = object()


class PluginError(ImportError):
    """A plugin could not be loaded; ``__cause__`` is the original error."""


@dataclass
class Plugin:
    """One entry point: imported on the first ``load`` and cached.

    Attributes:
        name: the entry point's name, the key in ``discover``'s result.
        group: its group, such as ``"modelly.spaces"``.
        value: the ``module:attribute`` it points to.
        distribution: the installed distribution that declares it, if known.
    """

    name: str
    group: str
    value: str
    distribution: str | None
    _entry_point: EntryPoint = field(repr=False, compare=False)
    _loaded: Any = field(default=_UNLOADED, repr=False, compare=False)

    def load(self) -> Any:
        """Import and return the object the entry point names.

        Raises:
            PluginError: if importing or resolving it fails, with the original error
                as its cause.
        """
        if self._loaded is _UNLOADED:
            try:
                self._loaded = self._entry_point.load()
            # Any error of third-party import code is isolated to this one plugin.
            except Exception as error:
                raise PluginError(
                    f"Plugin {self.name!r} ({self.value}) of group {self.group!r} "
                    f"from {self.distribution or 'an unknown distribution'} "
                    f"failed to load: {error}"
                ) from error
        return self._loaded

    __call__ = load


def _plugin(entry_point: EntryPoint, group: str) -> Plugin:
    """A ``Plugin`` for ``entry_point``, with the name of its distribution."""
    dist = getattr(entry_point, "dist", None)
    name = dist.metadata["Name"] if dist is not None else None
    return Plugin(entry_point.name, group, entry_point.value, name, entry_point)


def discover(group: str) -> dict[str, Plugin]:
    """The installed plugins of ``group``, by name, sorted; nothing is imported.

    Any group name works, so a feature may define its own; ``GROUPS`` lists Modelly's.
    When two distributions declare the same name, the first distribution in
    alphabetical order wins and a ``RuntimeWarning`` names both.

    Example:
        >>> discover("modelly.no_such_group")
        {}
    """
    found: dict[str, Plugin] = {}
    plugins = [_plugin(ep, group) for ep in entry_points(group=group)]
    for plugin in sorted(plugins, key=lambda p: (p.name, p.distribution or "")):
        if plugin.name in found:
            warnings.warn(
                f"Plugin {plugin.name!r} of {group!r} is declared by "
                f"{found[plugin.name].distribution} and {plugin.distribution}; "
                f"using {found[plugin.name].distribution}.",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        found[plugin.name] = plugin
    return found


def load_all(group: str) -> tuple[dict[str, Any], dict[str, PluginError]]:
    """Load every plugin of ``group``: ``(objects by name, errors by name)``.

    A plugin that fails is reported in the second dictionary; the others still load.
    """
    loaded: dict[str, Any] = {}
    errors: dict[str, PluginError] = {}
    for name, plugin in discover(group).items():
        try:
            loaded[name] = plugin.load()
        except PluginError as error:
            errors[name] = error
    return loaded, errors
