"""Generic plugin registry backed by Python entry points.

Renderers and publishers are discovered from the ``narrate.renderers`` and
``narrate.publishers`` entry-point groups, so third-party packages extend
Narrate by declaring an entry point -- no core code changes required.
Plugins can also be registered programmatically, which is how tests and
embedders inject fakes.
"""

from __future__ import annotations

from importlib import metadata
from typing import ClassVar, Protocol, runtime_checkable

from narrate.exceptions import PluginNotFoundError

__all__ = ["Named", "PluginRegistry"]


@runtime_checkable
class Named(Protocol):
    """Anything with a ``name`` attribute usable as a registry key."""

    name: ClassVar[str]


class PluginRegistry[PluginT: Named]:
    """A lazy, name-keyed registry of plugin instances.

    Entry points are loaded on first access so importing Narrate stays
    cheap and a broken third-party plugin cannot break unrelated commands.
    A plugin whose entry point fails to load is skipped and remembered as
    an error, which is surfaced if that plugin is then requested by name.
    """

    def __init__(self, kind: str, entry_point_group: str | None = None) -> None:
        """Initialise the registry.

        Args:
            kind: Human readable plugin category (used in errors).
            entry_point_group: Entry-point group to discover from, or
                ``None`` for a purely programmatic registry.
        """
        self._kind = kind
        self._group = entry_point_group
        self._plugins: dict[str, PluginT] = {}
        self._load_errors: dict[str, str] = {}
        self._discovered = False

    def register(self, plugin: PluginT, *, replace: bool = False) -> None:
        """Register a plugin instance under its ``name``.

        Args:
            plugin: The plugin to register.
            replace: Allow overwriting an existing registration.

        Raises:
            ValueError: If the name is taken and ``replace`` is false.
        """
        self._ensure_discovered()
        if not replace and plugin.name in self._plugins:
            msg = f"{self._kind} {plugin.name!r} is already registered"
            raise ValueError(msg)
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> PluginT:
        """Return the plugin registered under ``name``.

        Raises:
            PluginNotFoundError: If no such plugin is registered.  If the
                plugin exists but failed to load, the load error is
                included in the message.
        """
        self._ensure_discovered()
        plugin = self._plugins.get(name)
        if plugin is None:
            detail = self._load_errors.get(name)
            if detail is not None:
                msg = f"{self._kind} {name!r} failed to load: {detail}"
                raise PluginNotFoundError(self._kind, name, self.names()) from RuntimeError(msg)
            raise PluginNotFoundError(self._kind, name, self.names())
        return plugin

    def names(self) -> list[str]:
        """Return the sorted names of all loadable plugins."""
        self._ensure_discovered()
        return sorted(self._plugins)

    def all(self) -> list[PluginT]:
        """Return all loadable plugins sorted by name."""
        self._ensure_discovered()
        return [self._plugins[name] for name in self.names()]

    def _ensure_discovered(self) -> None:
        if self._discovered or self._group is None:
            self._discovered = True
            return
        self._discovered = True
        for entry_point in metadata.entry_points(group=self._group):
            try:
                plugin_cls = entry_point.load()
                plugin: PluginT = plugin_cls()
            except Exception as exc:
                self._load_errors[entry_point.name] = f"{type(exc).__name__}: {exc}"
                continue
            self._plugins.setdefault(plugin.name, plugin)
