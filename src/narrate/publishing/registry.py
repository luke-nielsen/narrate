"""Registry of publisher plugins."""

from __future__ import annotations

from narrate.plugins import PluginRegistry
from narrate.publishing.base import Publisher

__all__ = ["PublisherRegistry"]

ENTRY_POINT_GROUP = "narrate.publishers"


class PublisherRegistry(PluginRegistry[Publisher]):
    """Publisher registry discovered from ``narrate.publishers`` entry points."""

    def __init__(self, *, discover: bool = True) -> None:
        """Initialise the registry.

        Args:
            discover: Load plugins from entry points (disable in tests to
                start from an empty registry).
        """
        super().__init__("publisher", ENTRY_POINT_GROUP if discover else None)
