"""The 2.0 inventory: every deprecation that warns now, and every change 2.0 makes.

This is the record ``docs/deprecations.md`` is written from and that ``modelly migrate
--check-2.0`` will read: each ``Deprecation`` names the warning Modelly raises, its
replacement and the identifiers that find it in a project's code; each ``Change`` is one 2.0
epic's effect on user code and when it starts to warn. Tests check that every
``deprecated()`` call in ``modelly/`` is listed here, that the documentation's tables match,
and that each change points at an epic of the 2.0 roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass

REMOVAL = "2.0"


@dataclass(frozen=True)
class Deprecation:
    """A name or a use that warns now and is removed in 2.0.

    Attributes:
        doc: its row in the "Deprecated now" table of ``docs/deprecations.md``.
        replacement: what to use instead, as the table says.
        since: the release that started warning.
        module: the module whose ``deprecated()`` calls raise it.
        warnings: the names those calls pass (empty when the module builds them).
        find: identifiers that point at the deprecated use in a project's code.
    """

    doc: str
    replacement: str
    since: str
    module: str
    warnings: tuple[str, ...]
    find: tuple[str, ...]


@dataclass(frozen=True)
class Change:
    """One change of 2.0 to user code.

    Attributes:
        epic: the 2.0 roadmap epic, ``"H1"`` to ``"H11"``.
        summary: what changes.
        warns: ``"now"`` when every affected call warns already, ``"pending"`` when it will
            warn once its replacement ships in 1.x, ``"never"`` when no call changes (the
            numbers or a file format do; the migration guide covers it).
        reason: for ``"pending"`` and ``"never"``, why.
    """

    epic: str
    summary: str
    warns: str
    reason: str = ""


VIZ = "modelly.viz"
DEPRECATIONS: tuple[Deprecation, ...] = (
    Deprecation("`make_space_altair()`", "`make_altair_space()`", "1.0",
                f"{VIZ}.altair.components", ("make_space_altair()",), ("make_space_altair",)),
    Deprecation("`make_space_matplotlib()`", "`make_mpl_space_component()`", "1.0",
                f"{VIZ}.mpl.components", ("make_space_matplotlib()",), ("make_space_matplotlib",)),
    Deprecation("`make_plot_measure()`", "`make_mpl_plot_component()`", "1.0",
                f"{VIZ}.mpl.components", ("make_plot_measure()",), ("make_plot_measure",)),
    Deprecation("returning a dict from `agent_portrayal`", "an `AgentPortrayalStyle`", "1.0",
                f"{VIZ}.render.portrayal", ("Returning a dict from agent_portrayal",),
                ("agent_portrayal",)),
    Deprecation("a `property_layer_portrayal` dict", "a callable returning a `PropertyLayerStyle`",
                "1.0", f"{VIZ}.render.portrayal", ("The property_layer_portrayal dict",),
                ("property_layer_portrayal",)),
    Deprecation("`SpaceRenderer.render(...)` with arguments",
                "`setup_structure()`, `setup_agents()` and `setup_property_layer()`, then `render()`",
                "1.0", f"{VIZ}.render.legacy_args", ("Passing parameters to render()",), ("render",)),
    Deprecation("`draw_agents(agent_portrayal, **kwargs)`",
                "`setup_agents(agent_portrayal, **kwargs)`, then `draw_agents()`", "1.0",
                f"{VIZ}.render.legacy_args",
                ("draw_agents(agent_portrayal)", "draw_agents(**kwargs)"), ("draw_agents",)),
    Deprecation("`draw_structure(**kwargs)`", "`setup_structure(**kwargs)`, then `draw_structure()`",
                "1.0", f"{VIZ}.render.legacy_args", ("draw_structure(**kwargs)",), ("draw_structure",)),
    Deprecation("`draw_property_layer(property_layer_portrayal)`",
                "`setup_property_layer(...)`, then `draw_property_layer()`", "1.0",
                f"{VIZ}.render.legacy_args", ("draw_property_layer(property_layer_portrayal)",),
                ("draw_property_layer",)),
    Deprecation("`modelly.space.geo.ipf`, `modelly.space.geo.synthesize_population` (and the "
                "same names in `modelly.space.geo.population`)",
                "`modelly.population.ipf`, `modelly.population.synthesize_population`", "1.4",
                "modelly.space.geo.population", (), ("ipf", "synthesize_population")),
    Deprecation("`modelly.space.geo.population.MAX_ITERATIONS`, `REGION`, `TOLERANCE`",
                "the same names in `modelly.population.fitting`", "1.4",
                "modelly.space.geo.population", (), ("MAX_ITERATIONS", "REGION", "TOLERANCE")),
    Deprecation("a `Scenario` subclass attribute without an annotation",
                "an annotated field (`beta: float = 0.3`)", "1.5", "modelly.scenarios.typed",
                (), ("Scenario",)),
    Deprecation("a parameter a `Scenario` subclass does not declare, or of another type than "
                "its annotation", "an annotated field, and a value of its type", "1.5",
                "modelly.scenarios.typed", (), ("Scenario",)),
)  # fmt: skip

CHANGES: tuple[Change, ...] = (
    Change("H1", "the synthetic-population helpers leave the geographic space", "now"),
    Change("H1", "every name deprecated in 1.3 to 1.5 is removed", "now"),
    Change("H6", "per-agent random streams become the default", "never",
           "the numbers drawn change, no call does; agent_streams = True gives them now"),
    Change("H2", "one space protocol; property layers become fields on every space", "never",
           "today's space classes stay as thin aliases through 2.x where they map cleanly; "
           "one that does not map warns in 2.x before it goes in 3.0"),
    Change("H3", "typed attributes become columns by default", "never",
           "models keep their attributes; only where they are stored changes"),
    Change("H4", "one clock, one documented tie-breaking order", "never",
           "1.x already orders events by time, priority, then insertion order, the 2.0 rule; "
           "docs/event_ordering.md and its tests pin it"),
    Change("H5", "Scenario becomes typed and validated, loadable from TOML and YAML", "now"),
    Change("H8", "checkpoint and result formats v2", "never",
           "1.x files keep loading in 1.x; modelly checkpoint upgrade converts them"),
    Change("H9", "Python 3.13 minimum", "never", "the package metadata says it"),
    Change("H10", "provisional names are reviewed; stable ones keep the policy", "never",
           "a provisional name that changes gets a changelog entry and, where it can, a warning"),
)  # fmt: skip


def pending() -> list[Change]:
    """The changes that should warn in 1.x and do not yet: 1.5.0 ships with none."""
    return [change for change in CHANGES if change.warns == "pending"]
