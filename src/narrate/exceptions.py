"""Exception hierarchy for Narrate.

Every error raised intentionally by Narrate derives from
:class:`NarrateError` so callers can catch platform errors with a single
``except`` clause while letting programming errors propagate.
"""

from __future__ import annotations

__all__ = [
    "ArtifactIntegrityError",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "InvalidTransitionError",
    "NarrateError",
    "PluginNotFoundError",
    "PublishError",
    "RenderError",
]


class NarrateError(Exception):
    """Base class for all errors raised by Narrate."""


class EntityNotFoundError(NarrateError):
    """A requested entity does not exist in storage."""

    def __init__(self, entity: str, identifier: str) -> None:
        """Initialise the error.

        Args:
            entity: Human readable entity type, e.g. ``"project"``.
            identifier: The identifier that failed to resolve.
        """
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier!r}")


class DuplicateEntityError(NarrateError):
    """An entity with the same unique key already exists."""

    def __init__(self, entity: str, identifier: str) -> None:
        """Initialise the error.

        Args:
            entity: Human readable entity type, e.g. ``"project"``.
            identifier: The unique key that already exists.
        """
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} already exists: {identifier!r}")


class InvalidTransitionError(NarrateError):
    """A task or artifact was moved to a state it cannot legally reach."""


class PluginNotFoundError(NarrateError):
    """No plugin with the requested name is registered."""

    def __init__(self, kind: str, name: str, available: list[str]) -> None:
        """Initialise the error.

        Args:
            kind: Plugin category, e.g. ``"renderer"``.
            name: The requested plugin name.
            available: Names that *are* registered, for the error message.
        """
        self.kind = kind
        self.name = name
        self.available = available
        choices = ", ".join(sorted(available)) or "<none>"
        super().__init__(f"{kind} not found: {name!r} (available: {choices})")


class RenderError(NarrateError):
    """A renderer failed to produce output."""


class PublishError(NarrateError):
    """A publisher failed to deliver content to its destination."""


class ArtifactIntegrityError(NarrateError):
    """Stored artifact content does not match its recorded content hash."""
