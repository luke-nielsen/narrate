"""Composition root: builds and wires the standard object graph.

Every interface (CLI, MCP server, tests, embedders) obtains its
:class:`~narrate.orchestration.engine.Orchestrator` from a
:class:`Container`, keeping construction logic in exactly one place.
Tests swap pieces by constructing an ``Orchestrator`` directly with
fakes -- the engine itself only sees injected dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from narrate.config import NarrateSettings
from narrate.orchestration.engine import Orchestrator
from narrate.publishing.registry import PublisherRegistry
from narrate.rendering.registry import RendererRegistry
from narrate.storage.blob_store import BlobStore
from narrate.storage.database import Database

if TYPE_CHECKING:
    from types import TracebackType

__all__ = ["Container"]


class Container:
    """Owns the wired object graph for one Narrate deployment."""

    def __init__(self, settings: NarrateSettings | None = None) -> None:
        """Build the graph from settings.

        Args:
            settings: Configuration; resolved from the environment when
                omitted.  Directories and the database schema are created
                eagerly so the container is ready to use.
        """
        self.settings = settings or NarrateSettings()
        self.settings.ensure_directories()
        self.database = Database(self.settings.resolved_database_url, echo=self.settings.echo_sql)
        self.database.create_schema()
        self.blobs = BlobStore(self.settings.resolved_blobs_dir)
        self.renderers = RendererRegistry()
        self.publishers = PublisherRegistry()
        self.orchestrator = Orchestrator(
            self.database,
            self.blobs,
            self.renderers,
            self.publishers,
            self.settings.resolved_workspace_dir,
            default_agent_name=self.settings.default_agent_name,
        )

    def close(self) -> None:
        """Release database connections."""
        self.database.dispose()

    def __enter__(self) -> Self:
        """Support ``with Container() as container:`` usage."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the container on context exit."""
        self.close()
