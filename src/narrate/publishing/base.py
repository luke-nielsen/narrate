"""Publisher plugin contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Mapping

    from narrate.models import Artifact

__all__ = ["PublishReceipt", "PublishRequest", "Publisher"]


@dataclass(frozen=True, slots=True)
class PublishRequest:
    """Everything a publisher needs to deliver an artifact.

    Attributes:
        artifact: Metadata of the artifact being published.
        content: The artifact's bytes.
        destination: Publisher-specific destination (a directory path,
            site root, URL, ...).
        options: Publisher-specific options supplied by the caller.
    """

    artifact: Artifact
    content: bytes
    destination: str
    options: Mapping[str, Any] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        """Return a collision-safe filename for the artifact."""
        stem, dot, suffix = self.artifact.name.rpartition(".")
        if not dot:
            return f"{self.artifact.name}.v{self.artifact.version}"
        return f"{stem}.v{self.artifact.version}.{suffix}"


@dataclass(frozen=True, slots=True)
class PublishReceipt:
    """Proof of delivery returned by a publisher.

    Attributes:
        location: Where the content ended up (path or URL), if known.
        detail: Human readable notes about the delivery.
        metadata: Publisher-provided annotations persisted with the
            publication record.
    """

    location: str | None = None
    detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Publisher(ABC):
    """Base class for publisher plugins.

    Attributes:
        name: Unique registry key, also used in CLI/MCP calls.
        description: One-line summary shown in plugin listings.
    """

    name: ClassVar[str]
    description: ClassVar[str] = ""

    @abstractmethod
    def publish(self, request: PublishRequest) -> PublishReceipt:
        """Deliver content to the destination.

        Args:
            request: Artifact content, metadata, destination, options.

        Returns:
            A receipt describing where the content landed.

        Raises:
            PublishError: If delivery fails.
        """
