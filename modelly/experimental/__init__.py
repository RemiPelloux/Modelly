"""Experimental features package for Modelly.

This package contains modules that are under active development and testing. These
features are provided to allow early access and feedback from the Modelly community, but
their APIs may change between releases without following semantic versioning.

Current experimental modules:
    signals: Reactive programming capabilities for tracking state changes

Notes:
    - Features in this package may be changed or removed without notice
    - APIs are not guaranteed to be stable between releases
    - Features graduate from experimental status once their APIs are stabilized
"""

from modelly.experimental import actions, continuous_space, meta_agents, signals

__all__ = ["actions", "continuous_space", "meta_agents", "signals"]
