"""SQLAlchemy ORM table definitions.

ORM rows are an implementation detail of the storage layer: everything
above repositories speaks Pydantic domain models.  Each row class knows
how to convert itself to its domain twin via ``to_domain``.

SQLite discards timezone info, so datetimes are normalised back to UTC on
the way out.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from narrate.models import (
    Artifact,
    ArtifactKind,
    DocumentationGoal,
    DocumentationTask,
    Feature,
    Project,
    Publication,
    PublicationStatus,
    TaskStatus,
)

__all__ = [
    "ArtifactRow",
    "Base",
    "FeatureRow",
    "GoalRow",
    "ProjectRow",
    "PublicationRow",
    "TaskRow",
]


def _as_utc(value: datetime) -> datetime:
    """Attach UTC to naive datetimes coming back from SQLite."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Declarative base for all Narrate tables."""

    type_annotation_map = {dict[str, Any]: JSON}  # noqa: RUF012


class ProjectRow(Base):
    """Relational representation of :class:`~narrate.models.Project`."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    application_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    repository_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    tags: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_domain(self) -> Project:
        """Convert this row to its domain model."""
        return Project(
            id=self.id,
            slug=self.slug,
            name=self.name,
            description=self.description,
            application_url=self.application_url,
            repository_url=self.repository_url,
            tags=tuple(self.tags.get("values", [])),
            created_at=_as_utc(self.created_at),
        )

    @classmethod
    def from_domain(cls, project: Project) -> ProjectRow:
        """Build a row from a domain model."""
        return cls(
            id=project.id,
            slug=project.slug,
            name=project.name,
            description=project.description,
            application_url=project.application_url,
            repository_url=project.repository_url,
            tags={"values": list(project.tags)},
            created_at=project.created_at,
        )


class FeatureRow(Base):
    """Relational representation of :class:`~narrate.models.Feature`."""

    __tablename__ = "features"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_feature_project_slug"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    slug: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    url_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_domain(self) -> Feature:
        """Convert this row to its domain model."""
        return Feature(
            id=self.id,
            project_id=self.project_id,
            slug=self.slug,
            name=self.name,
            description=self.description,
            url_path=self.url_path,
            priority=self.priority,
            created_at=_as_utc(self.created_at),
        )

    @classmethod
    def from_domain(cls, feature: Feature) -> FeatureRow:
        """Build a row from a domain model."""
        return cls(
            id=feature.id,
            project_id=feature.project_id,
            slug=feature.slug,
            name=feature.name,
            description=feature.description,
            url_path=feature.url_path,
            priority=feature.priority,
            created_at=feature.created_at,
        )


class GoalRow(Base):
    """Relational representation of :class:`~narrate.models.DocumentationGoal`."""

    __tablename__ = "goals"
    __table_args__ = (UniqueConstraint("project_id", "kind", name="uq_goal_project_kind"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    audience: Mapped[str] = mapped_column(String(200), default="end users")
    tone: Mapped[str] = mapped_column(String(200), default="clear and friendly")
    instructions: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_domain(self) -> DocumentationGoal:
        """Convert this row to its domain model."""
        return DocumentationGoal(
            id=self.id,
            project_id=self.project_id,
            kind=ArtifactKind(self.kind),
            audience=self.audience,
            tone=self.tone,
            instructions=self.instructions,
            created_at=_as_utc(self.created_at),
        )

    @classmethod
    def from_domain(cls, goal: DocumentationGoal) -> GoalRow:
        """Build a row from a domain model."""
        return cls(
            id=goal.id,
            project_id=goal.project_id,
            kind=goal.kind.value,
            audience=goal.audience,
            tone=goal.tone,
            instructions=goal.instructions,
            created_at=goal.created_at,
        )


class TaskRow(Base):
    """Relational representation of :class:`~narrate.models.DocumentationTask`."""

    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("feature_id", "goal_id", name="uq_task_feature_goal"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    feature_id: Mapped[str] = mapped_column(ForeignKey("features.id"), index=True)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    instructions: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value, index=True)
    claimed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_domain(self) -> DocumentationTask:
        """Convert this row to its domain model."""
        return DocumentationTask(
            id=self.id,
            project_id=self.project_id,
            feature_id=self.feature_id,
            goal_id=self.goal_id,
            kind=ArtifactKind(self.kind),
            title=self.title,
            instructions=self.instructions,
            status=TaskStatus(self.status),
            claimed_by=self.claimed_by,
            artifact_id=self.artifact_id,
            error=self.error,
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )

    @classmethod
    def from_domain(cls, task: DocumentationTask) -> TaskRow:
        """Build a row from a domain model."""
        return cls(
            id=task.id,
            project_id=task.project_id,
            feature_id=task.feature_id,
            goal_id=task.goal_id,
            kind=task.kind.value,
            title=task.title,
            instructions=task.instructions,
            status=task.status.value,
            claimed_by=task.claimed_by,
            artifact_id=task.artifact_id,
            error=task.error,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class ArtifactRow(Base):
    """Relational representation of :class:`~narrate.models.Artifact`."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    feature_id: Mapped[str | None] = mapped_column(
        ForeignKey("features.id"), nullable=True, index=True
    )
    task_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    media_type: Mapped[str] = mapped_column(String(200), default="text/plain")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(200), default="unknown")
    derived_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    renderer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_domain(self) -> Artifact:
        """Convert this row to its domain model."""
        return Artifact(
            id=self.id,
            project_id=self.project_id,
            feature_id=self.feature_id,
            task_id=self.task_id,
            kind=ArtifactKind(self.kind),
            name=self.name,
            version=self.version,
            media_type=self.media_type,
            content_hash=self.content_hash,
            size_bytes=self.size_bytes,
            created_by=self.created_by,
            derived_from=self.derived_from,
            renderer=self.renderer,
            metadata=dict(self.meta),
            created_at=_as_utc(self.created_at),
        )

    @classmethod
    def from_domain(cls, artifact: Artifact) -> ArtifactRow:
        """Build a row from a domain model."""
        return cls(
            id=artifact.id,
            project_id=artifact.project_id,
            feature_id=artifact.feature_id,
            task_id=artifact.task_id,
            kind=artifact.kind.value,
            name=artifact.name,
            version=artifact.version,
            media_type=artifact.media_type,
            content_hash=artifact.content_hash,
            size_bytes=artifact.size_bytes,
            created_by=artifact.created_by,
            derived_from=artifact.derived_from,
            renderer=artifact.renderer,
            meta=dict(artifact.metadata),
            created_at=artifact.created_at,
        )


class PublicationRow(Base):
    """Relational representation of :class:`~narrate.models.Publication`."""

    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), index=True)
    publisher: Mapped[str] = mapped_column(String(100))
    destination: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20))
    location: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_domain(self) -> Publication:
        """Convert this row to its domain model."""
        return Publication(
            id=self.id,
            artifact_id=self.artifact_id,
            publisher=self.publisher,
            destination=self.destination,
            status=PublicationStatus(self.status),
            location=self.location,
            detail=self.detail,
            metadata=dict(self.meta),
            created_at=_as_utc(self.created_at),
        )

    @classmethod
    def from_domain(cls, publication: Publication) -> PublicationRow:
        """Build a row from a domain model."""
        return cls(
            id=publication.id,
            artifact_id=publication.artifact_id,
            publisher=publication.publisher,
            destination=publication.destination,
            status=publication.status.value,
            location=publication.location,
            detail=publication.detail,
            meta=dict(publication.metadata),
            created_at=publication.created_at,
        )
