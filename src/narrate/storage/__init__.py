"""Persistence layer: relational metadata plus a content-addressed blob store.

Structured metadata (projects, features, goals, tasks, artifacts,
publications) lives in any SQLAlchemy-supported database.  Artifact
*content* lives in :class:`~narrate.storage.blob_store.BlobStore`,
addressed by SHA-256 so identical content is stored once and integrity is
verifiable on read.
"""

from narrate.storage.blob_store import BlobStore
from narrate.storage.database import Database
from narrate.storage.repositories import (
    ArtifactRepository,
    FeatureRepository,
    GoalRepository,
    ProjectRepository,
    PublicationRepository,
    TaskRepository,
)

__all__ = [
    "ArtifactRepository",
    "BlobStore",
    "Database",
    "FeatureRepository",
    "GoalRepository",
    "ProjectRepository",
    "PublicationRepository",
    "TaskRepository",
]
