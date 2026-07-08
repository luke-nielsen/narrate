"""Repositories translating between domain models and ORM rows.

Each repository wraps a live :class:`~sqlalchemy.orm.Session` supplied by
the caller (typically the orchestration engine, which owns transaction
boundaries).  Repositories accept and return domain models only; ORM rows
never escape this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from narrate.exceptions import DuplicateEntityError, EntityNotFoundError
from narrate.models import (
    Artifact,
    ArtifactKind,
    DocumentationGoal,
    DocumentationTask,
    Feature,
    Project,
    Publication,
    TaskStatus,
    utcnow,
)
from narrate.storage.orm import (
    ArtifactRow,
    FeatureRow,
    GoalRow,
    ProjectRow,
    PublicationRow,
    TaskRow,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "ArtifactRepository",
    "FeatureRepository",
    "GoalRepository",
    "ProjectRepository",
    "PublicationRepository",
    "TaskRepository",
]


class _Repository:
    """Shared session plumbing for all repositories."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an active session."""
        self._session = session


class ProjectRepository(_Repository):
    """Persistence operations for :class:`~narrate.models.Project`."""

    def add(self, project: Project) -> Project:
        """Insert a new project.

        Raises:
            DuplicateEntityError: If the slug is already taken.
        """
        existing = self._session.scalar(select(ProjectRow).where(ProjectRow.slug == project.slug))
        if existing is not None:
            raise DuplicateEntityError("project", project.slug)
        self._session.add(ProjectRow.from_domain(project))
        return project

    def get(self, project_id: str) -> Project:
        """Fetch a project by id.

        Raises:
            EntityNotFoundError: If no such project exists.
        """
        row = self._session.get(ProjectRow, project_id)
        if row is None:
            raise EntityNotFoundError("project", project_id)
        return row.to_domain()

    def get_by_slug(self, slug: str) -> Project:
        """Fetch a project by slug.

        Raises:
            EntityNotFoundError: If no such project exists.
        """
        row = self._session.scalar(select(ProjectRow).where(ProjectRow.slug == slug))
        if row is None:
            raise EntityNotFoundError("project", slug)
        return row.to_domain()

    def resolve(self, ref: str) -> Project:
        """Fetch a project by id *or* slug.

        Raises:
            EntityNotFoundError: If neither interpretation matches.
        """
        row = self._session.get(ProjectRow, ref) or self._session.scalar(
            select(ProjectRow).where(ProjectRow.slug == ref)
        )
        if row is None:
            raise EntityNotFoundError("project", ref)
        return row.to_domain()

    def list(self) -> Sequence[Project]:
        """Return all projects ordered by slug."""
        rows = self._session.scalars(select(ProjectRow).order_by(ProjectRow.slug)).all()
        return [row.to_domain() for row in rows]


class FeatureRepository(_Repository):
    """Persistence operations for :class:`~narrate.models.Feature`."""

    def add(self, feature: Feature) -> Feature:
        """Insert a new feature.

        Raises:
            DuplicateEntityError: If the (project, slug) pair exists.
        """
        existing = self._session.scalar(
            select(FeatureRow).where(
                FeatureRow.project_id == feature.project_id,
                FeatureRow.slug == feature.slug,
            )
        )
        if existing is not None:
            raise DuplicateEntityError("feature", f"{feature.project_id}/{feature.slug}")
        self._session.add(FeatureRow.from_domain(feature))
        return feature

    def get(self, feature_id: str) -> Feature:
        """Fetch a feature by id.

        Raises:
            EntityNotFoundError: If no such feature exists.
        """
        row = self._session.get(FeatureRow, feature_id)
        if row is None:
            raise EntityNotFoundError("feature", feature_id)
        return row.to_domain()

    def get_by_slug(self, project_id: str, slug: str) -> Feature:
        """Fetch a feature by (project, slug).

        Raises:
            EntityNotFoundError: If no such feature exists.
        """
        row = self._session.scalar(
            select(FeatureRow).where(FeatureRow.project_id == project_id, FeatureRow.slug == slug)
        )
        if row is None:
            raise EntityNotFoundError("feature", f"{project_id}/{slug}")
        return row.to_domain()

    def list_for_project(self, project_id: str) -> Sequence[Feature]:
        """Return a project's features ordered by priority then slug."""
        rows = self._session.scalars(
            select(FeatureRow)
            .where(FeatureRow.project_id == project_id)
            .order_by(FeatureRow.priority, FeatureRow.slug)
        ).all()
        return [row.to_domain() for row in rows]


class GoalRepository(_Repository):
    """Persistence operations for :class:`~narrate.models.DocumentationGoal`."""

    def add(self, goal: DocumentationGoal) -> DocumentationGoal:
        """Insert a new goal.

        Raises:
            DuplicateEntityError: If the project already has a goal for
                this artifact kind.
        """
        existing = self._session.scalar(
            select(GoalRow).where(
                GoalRow.project_id == goal.project_id, GoalRow.kind == goal.kind.value
            )
        )
        if existing is not None:
            raise DuplicateEntityError("goal", f"{goal.project_id}/{goal.kind.value}")
        self._session.add(GoalRow.from_domain(goal))
        return goal

    def get(self, goal_id: str) -> DocumentationGoal:
        """Fetch a goal by id.

        Raises:
            EntityNotFoundError: If no such goal exists.
        """
        row = self._session.get(GoalRow, goal_id)
        if row is None:
            raise EntityNotFoundError("goal", goal_id)
        return row.to_domain()

    def list_for_project(self, project_id: str) -> Sequence[DocumentationGoal]:
        """Return a project's goals ordered by kind."""
        rows = self._session.scalars(
            select(GoalRow).where(GoalRow.project_id == project_id).order_by(GoalRow.kind)
        ).all()
        return [row.to_domain() for row in rows]


class TaskRepository(_Repository):
    """Persistence operations for :class:`~narrate.models.DocumentationTask`."""

    def add(self, task: DocumentationTask) -> DocumentationTask:
        """Insert a new task."""
        self._session.add(TaskRow.from_domain(task))
        return task

    def get(self, task_id: str) -> DocumentationTask:
        """Fetch a task by id.

        Raises:
            EntityNotFoundError: If no such task exists.
        """
        row = self._row(task_id)
        return row.to_domain()

    def exists_for(self, feature_id: str, goal_id: str) -> bool:
        """Return whether a task already exists for (feature, goal)."""
        row = self._session.scalar(
            select(TaskRow).where(TaskRow.feature_id == feature_id, TaskRow.goal_id == goal_id)
        )
        return row is not None

    def list_for_project(
        self,
        project_id: str,
        *,
        status: TaskStatus | None = None,
    ) -> Sequence[DocumentationTask]:
        """Return a project's tasks, optionally filtered by status."""
        stmt = select(TaskRow).where(TaskRow.project_id == project_id)
        if status is not None:
            stmt = stmt.where(TaskRow.status == status.value)
        rows = self._session.scalars(stmt.order_by(TaskRow.created_at, TaskRow.id)).all()
        return [row.to_domain() for row in rows]

    def list_pending(self, project_id: str | None = None) -> Sequence[DocumentationTask]:
        """Return pending tasks, optionally scoped to one project."""
        stmt = select(TaskRow).where(TaskRow.status == TaskStatus.PENDING.value)
        if project_id is not None:
            stmt = stmt.where(TaskRow.project_id == project_id)
        rows = self._session.scalars(stmt.order_by(TaskRow.created_at, TaskRow.id)).all()
        return [row.to_domain() for row in rows]

    def update(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        claimed_by: str | None = None,
        artifact_id: str | None = None,
        error: str | None = None,
    ) -> DocumentationTask:
        """Apply a partial update to a task and return the new state.

        Only the fields passed as non-``None`` are changed;
        ``updated_at`` is always refreshed.

        Raises:
            EntityNotFoundError: If no such task exists.
        """
        row = self._row(task_id)
        if status is not None:
            row.status = status.value
        if claimed_by is not None:
            row.claimed_by = claimed_by
        if artifact_id is not None:
            row.artifact_id = artifact_id
        if error is not None:
            row.error = error
        row.updated_at = utcnow()
        self._session.flush()
        return row.to_domain()

    def counts_by_status(self, project_id: str) -> dict[str, int]:
        """Return ``{status_value: count}`` for a project's tasks."""
        stmt = (
            select(TaskRow.status, func.count())
            .where(TaskRow.project_id == project_id)
            .group_by(TaskRow.status)
        )
        rows = self._session.execute(stmt).all()
        return {str(status): int(count) for status, count in rows}

    def _row(self, task_id: str) -> TaskRow:
        row = self._session.get(TaskRow, task_id)
        if row is None:
            raise EntityNotFoundError("task", task_id)
        return row


class ArtifactRepository(_Repository):
    """Persistence operations for :class:`~narrate.models.Artifact`."""

    def add(self, artifact: Artifact) -> Artifact:
        """Insert a new artifact record."""
        self._session.add(ArtifactRow.from_domain(artifact))
        return artifact

    def get(self, artifact_id: str) -> Artifact:
        """Fetch an artifact by id.

        Raises:
            EntityNotFoundError: If no such artifact exists.
        """
        row = self._session.get(ArtifactRow, artifact_id)
        if row is None:
            raise EntityNotFoundError("artifact", artifact_id)
        return row.to_domain()

    def next_version(
        self,
        project_id: str,
        feature_id: str | None,
        kind: ArtifactKind,
        name: str,
    ) -> int:
        """Return the next version number for an artifact identity."""
        stmt = select(func.max(ArtifactRow.version)).where(
            ArtifactRow.project_id == project_id,
            ArtifactRow.feature_id == feature_id,
            ArtifactRow.kind == kind.value,
            ArtifactRow.name == name,
        )
        current = self._session.scalar(stmt)
        return (current or 0) + 1

    def list_for_project(
        self,
        project_id: str,
        *,
        feature_id: str | None = None,
        kind: ArtifactKind | None = None,
        latest_only: bool = False,
    ) -> Sequence[Artifact]:
        """Return artifacts for a project with optional filters.

        Args:
            project_id: Owning project id.
            feature_id: Restrict to one feature.
            kind: Restrict to one artifact kind.
            latest_only: Keep only the highest version per
                (feature, kind, name) identity.
        """
        stmt = select(ArtifactRow).where(ArtifactRow.project_id == project_id)
        if feature_id is not None:
            stmt = stmt.where(ArtifactRow.feature_id == feature_id)
        if kind is not None:
            stmt = stmt.where(ArtifactRow.kind == kind.value)
        rows = self._session.scalars(stmt.order_by(ArtifactRow.created_at, ArtifactRow.id)).all()
        artifacts = [row.to_domain() for row in rows]
        if latest_only:
            newest: dict[tuple[str | None, str, str], Artifact] = {}
            for artifact in artifacts:
                key = (artifact.feature_id, artifact.kind.value, artifact.name)
                held = newest.get(key)
                if held is None or artifact.version > held.version:
                    newest[key] = artifact
            artifacts = sorted(newest.values(), key=lambda a: (a.kind.value, a.name))
        return artifacts

    def count_for_project(self, project_id: str) -> int:
        """Return the total number of artifact records for a project."""
        stmt = (
            select(func.count())
            .select_from(ArtifactRow)
            .where(ArtifactRow.project_id == project_id)
        )
        return self._session.scalar(stmt) or 0


class PublicationRepository(_Repository):
    """Persistence operations for :class:`~narrate.models.Publication`."""

    def add(self, publication: Publication) -> Publication:
        """Insert a new publication record."""
        self._session.add(PublicationRow.from_domain(publication))
        return publication

    def list_for_artifact(self, artifact_id: str) -> Sequence[Publication]:
        """Return publications of one artifact, oldest first."""
        rows = self._session.scalars(
            select(PublicationRow)
            .where(PublicationRow.artifact_id == artifact_id)
            .order_by(PublicationRow.created_at, PublicationRow.id)
        ).all()
        return [row.to_domain() for row in rows]

    def count_succeeded_for_project(self, project_id: str) -> int:
        """Return the number of successful publications for a project."""
        stmt = (
            select(func.count())
            .select_from(PublicationRow)
            .join(ArtifactRow, ArtifactRow.id == PublicationRow.artifact_id)
            .where(
                ArtifactRow.project_id == project_id,
                PublicationRow.status == "succeeded",
            )
        )
        return self._session.scalar(stmt) or 0
