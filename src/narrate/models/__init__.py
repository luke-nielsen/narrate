"""Pydantic domain models shared across all Narrate layers.

These models are the *lingua franca* of the platform: repositories return
them, the orchestration engine operates on them, and the MCP server
serialises them to AI assistants.  They are frozen (immutable) so state
changes always flow through the storage layer.
"""

from narrate.models.entities import (
    Artifact,
    DocumentationGoal,
    DocumentationTask,
    Feature,
    Project,
    ProjectStatusReport,
    Publication,
)
from narrate.models.enums import ArtifactKind, PublicationStatus, TaskStatus
from narrate.models.support import new_id, utcnow

__all__ = [
    "Artifact",
    "ArtifactKind",
    "DocumentationGoal",
    "DocumentationTask",
    "Feature",
    "Project",
    "ProjectStatusReport",
    "Publication",
    "PublicationStatus",
    "TaskStatus",
    "new_id",
    "utcnow",
]
