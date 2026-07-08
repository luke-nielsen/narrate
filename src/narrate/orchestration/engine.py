"""The documentation lifecycle engine.

:class:`Orchestrator` is the facade every interface layer (CLI, MCP,
embedders) talks to.  It owns transaction boundaries and coordinates the
planner, blob store, and plugin registries; it contains *no* rendering or
publishing logic itself, so new plugins never require engine changes.
"""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING, Any

from narrate.exceptions import InvalidTransitionError, NarrateError, PublishError
from narrate.models import (
    Artifact,
    ArtifactKind,
    DocumentationGoal,
    DocumentationTask,
    Feature,
    Project,
    ProjectStatusReport,
    Publication,
    PublicationStatus,
    TaskStatus,
)
from narrate.models.support import slugify
from narrate.orchestration.planner import TaskPlanner
from narrate.publishing.base import PublishRequest
from narrate.rendering.base import RenderRequest
from narrate.storage.repositories import (
    ArtifactRepository,
    FeatureRepository,
    GoalRepository,
    ProjectRepository,
    PublicationRepository,
    TaskRepository,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from sqlalchemy.orm import Session

    from narrate.publishing.registry import PublisherRegistry
    from narrate.rendering.registry import RendererRegistry
    from narrate.storage.blob_store import BlobStore
    from narrate.storage.database import Database

__all__ = ["Orchestrator"]


class Orchestrator:
    """Coordinates the full documentation lifecycle.

    All dependencies are injected, so alternative storage backends,
    registries, or planners can be swapped in without subclassing.
    Construct one via :class:`narrate.container.Container` for the
    standard wiring.
    """

    def __init__(
        self,
        database: Database,
        blobs: BlobStore,
        renderers: RendererRegistry,
        publishers: PublisherRegistry,
        workspace_dir: Path,
        *,
        planner: TaskPlanner | None = None,
        default_agent_name: str = "unattributed-agent",
    ) -> None:
        """Wire the engine.

        Args:
            database: Session factory for relational metadata.
            blobs: Content-addressed store for artifact content.
            renderers: Registry of renderer plugins.
            publishers: Registry of publisher plugins.
            workspace_dir: Scratch space handed to renderers.
            planner: Task planning strategy (defaults to
                :class:`~narrate.orchestration.planner.TaskPlanner`).
            default_agent_name: Attribution when callers stay anonymous.
        """
        self._db = database
        self._blobs = blobs
        self._renderers = renderers
        self._publishers = publishers
        self._workspace_dir = workspace_dir
        self._planner = planner or TaskPlanner()
        self._default_agent = default_agent_name

    @property
    def renderers(self) -> RendererRegistry:
        """The renderer registry (for listing/registering plugins)."""
        return self._renderers

    @property
    def publishers(self) -> PublisherRegistry:
        """The publisher registry (for listing/registering plugins)."""
        return self._publishers

    # ------------------------------------------------------------------
    # Projects, features, goals
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        *,
        slug: str | None = None,
        description: str = "",
        application_url: str | None = None,
        repository_url: str | None = None,
        tags: Sequence[str] = (),
    ) -> Project:
        """Register a new project.

        Raises:
            DuplicateEntityError: If the slug is already taken.
        """
        project = Project(
            slug=slug or slugify(name),
            name=name,
            description=description,
            application_url=application_url,
            repository_url=repository_url,
            tags=tuple(tags),
        )
        with self._db.session() as session:
            return ProjectRepository(session).add(project)

    def list_projects(self) -> Sequence[Project]:
        """Return all projects."""
        with self._db.session() as session:
            return ProjectRepository(session).list()

    def get_project(self, ref: str) -> Project:
        """Return a project by id or slug.

        Raises:
            EntityNotFoundError: If no such project exists.
        """
        with self._db.session() as session:
            return ProjectRepository(session).resolve(ref)

    def add_feature(
        self,
        project_ref: str,
        name: str,
        *,
        slug: str | None = None,
        description: str = "",
        url_path: str | None = None,
        priority: int = 100,
    ) -> Feature:
        """Register a feature on a project.

        Raises:
            EntityNotFoundError: If the project does not exist.
            DuplicateEntityError: If the feature slug is taken.
        """
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            feature = Feature(
                project_id=project.id,
                slug=slug or slugify(name),
                name=name,
                description=description,
                url_path=url_path,
                priority=priority,
            )
            return FeatureRepository(session).add(feature)

    def list_features(self, project_ref: str) -> Sequence[Feature]:
        """Return a project's features ordered by priority."""
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            return FeatureRepository(session).list_for_project(project.id)

    def add_goal(
        self,
        project_ref: str,
        kind: ArtifactKind,
        *,
        audience: str = "end users",
        tone: str = "clear and friendly",
        instructions: str = "",
    ) -> DocumentationGoal:
        """Configure a documentation goal for a project.

        Raises:
            EntityNotFoundError: If the project does not exist.
            DuplicateEntityError: If a goal of this kind exists already.
        """
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            goal = DocumentationGoal(
                project_id=project.id,
                kind=kind,
                audience=audience,
                tone=tone,
                instructions=instructions,
            )
            return GoalRepository(session).add(goal)

    def list_goals(self, project_ref: str) -> Sequence[DocumentationGoal]:
        """Return a project's documentation goals."""
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            return GoalRepository(session).list_for_project(project.id)

    # ------------------------------------------------------------------
    # Task lifecycle
    # ------------------------------------------------------------------

    def plan(self, project_ref: str) -> Sequence[DocumentationTask]:
        """Expand goals against features into new pending tasks.

        Planning is idempotent: (feature, goal) pairs that already have a
        task -- in any status -- are skipped.

        Returns:
            Only the newly created tasks.
        """
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            features = FeatureRepository(session).list_for_project(project.id)
            goals = GoalRepository(session).list_for_project(project.id)
            tasks = TaskRepository(session)
            existing = [
                (task.feature_id, task.goal_id) for task in tasks.list_for_project(project.id)
            ]
            new_tasks = self._planner.plan(project, features, goals, existing)
            for task in new_tasks:
                tasks.add(task)
            return new_tasks

    def get_task(self, task_id: str) -> DocumentationTask:
        """Return a task by id.

        Raises:
            EntityNotFoundError: If no such task exists.
        """
        with self._db.session() as session:
            return TaskRepository(session).get(task_id)

    def list_tasks(
        self, project_ref: str, *, status: TaskStatus | None = None
    ) -> Sequence[DocumentationTask]:
        """Return a project's tasks, optionally filtered by status."""
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            return TaskRepository(session).list_for_project(project.id, status=status)

    def list_pending_tasks(self, project_ref: str | None = None) -> Sequence[DocumentationTask]:
        """Return pending tasks across all projects or one project."""
        with self._db.session() as session:
            project_id: str | None = None
            if project_ref is not None:
                project_id = ProjectRepository(session).resolve(project_ref).id
            return TaskRepository(session).list_pending(project_id)

    def claim_task(self, task_id: str, *, agent: str | None = None) -> DocumentationTask:
        """Move a pending task to in-progress on behalf of ``agent``.

        Raises:
            EntityNotFoundError: If no such task exists.
            InvalidTransitionError: If the task is not pending.
        """
        with self._db.session() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task.status is not TaskStatus.PENDING:
                msg = (
                    f"task {task_id} is {task.status.value}, only pending tasks can be "
                    f"claimed (claimed_by={task.claimed_by!r})"
                )
                raise InvalidTransitionError(msg)
            return tasks.update(
                task_id,
                status=TaskStatus.IN_PROGRESS,
                claimed_by=agent or self._default_agent,
            )

    def complete_task(self, task_id: str) -> DocumentationTask:
        """Mark an in-progress task as completed.

        Raises:
            InvalidTransitionError: If the task is not in progress or no
                artifact has been saved for it.
        """
        with self._db.session() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task.status is not TaskStatus.IN_PROGRESS:
                msg = f"task {task_id} is {task.status.value}, expected in_progress"
                raise InvalidTransitionError(msg)
            if task.artifact_id is None:
                msg = f"task {task_id} has no saved artifact; save one before completing"
                raise InvalidTransitionError(msg)
            return tasks.update(task_id, status=TaskStatus.COMPLETED)

    def fail_task(self, task_id: str, reason: str) -> DocumentationTask:
        """Mark a pending or in-progress task as failed.

        Raises:
            InvalidTransitionError: If the task already terminated.
        """
        with self._db.session() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task.status not in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                msg = f"task {task_id} is {task.status.value} and cannot fail"
                raise InvalidTransitionError(msg)
            return tasks.update(task_id, status=TaskStatus.FAILED, error=reason)

    def cancel_task(self, task_id: str) -> DocumentationTask:
        """Withdraw a pending or in-progress task.

        Raises:
            InvalidTransitionError: If the task already terminated.
        """
        with self._db.session() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task.status not in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                msg = f"task {task_id} is {task.status.value} and cannot be cancelled"
                raise InvalidTransitionError(msg)
            return tasks.update(task_id, status=TaskStatus.CANCELLED)

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def save_task_artifact(
        self,
        task_id: str,
        content: bytes,
        *,
        name: str | None = None,
        media_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        created_by: str | None = None,
    ) -> Artifact:
        """Store generated content as the artifact for a task.

        The task must be in progress.  Saving again creates a new version;
        the task always points at the most recent artifact.

        Raises:
            EntityNotFoundError: If no such task exists.
            InvalidTransitionError: If the task is not in progress.
        """
        with self._db.session() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task.status is not TaskStatus.IN_PROGRESS:
                msg = f"task {task_id} is {task.status.value}; claim it before saving artifacts"
                raise InvalidTransitionError(msg)
            feature = FeatureRepository(session).get(task.feature_id)
            artifact = self._store_artifact(
                session,
                project_id=task.project_id,
                feature_id=task.feature_id,
                task_id=task.id,
                kind=task.kind,
                name=name or f"{feature.slug}-{task.kind.value}{_source_suffix(task.kind)}",
                content=content,
                media_type=media_type,
                metadata=dict(metadata or {}),
                created_by=created_by or task.claimed_by or self._default_agent,
            )
            tasks.update(task_id, artifact_id=artifact.id)
            return artifact

    def save_artifact(
        self,
        project_ref: str,
        kind: ArtifactKind,
        name: str,
        content: bytes,
        *,
        feature_ref: str | None = None,
        media_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        created_by: str | None = None,
    ) -> Artifact:
        """Store content as a standalone (non-task) artifact.

        Raises:
            EntityNotFoundError: If the project or feature is missing.
        """
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            feature_id: str | None = None
            if feature_ref is not None:
                feature_id = FeatureRepository(session).get_by_slug(project.id, feature_ref).id
            return self._store_artifact(
                session,
                project_id=project.id,
                feature_id=feature_id,
                task_id=None,
                kind=kind,
                name=name,
                content=content,
                media_type=media_type,
                metadata=dict(metadata or {}),
                created_by=created_by or self._default_agent,
            )

    def get_artifact(self, artifact_id: str) -> Artifact:
        """Return artifact metadata by id.

        Raises:
            EntityNotFoundError: If no such artifact exists.
        """
        with self._db.session() as session:
            return ArtifactRepository(session).get(artifact_id)

    def read_artifact(self, artifact_id: str) -> tuple[Artifact, bytes]:
        """Return an artifact together with its content bytes.

        Raises:
            EntityNotFoundError: If no such artifact exists.
            ArtifactIntegrityError: If stored content is corrupt.
        """
        with self._db.session() as session:
            artifact = ArtifactRepository(session).get(artifact_id)
        return artifact, self._blobs.get(artifact.content_hash)

    def list_artifacts(
        self,
        project_ref: str,
        *,
        feature_ref: str | None = None,
        kind: ArtifactKind | None = None,
        latest_only: bool = False,
    ) -> Sequence[Artifact]:
        """Return a project's artifacts with optional filters."""
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            feature_id: str | None = None
            if feature_ref is not None:
                feature_id = FeatureRepository(session).get_by_slug(project.id, feature_ref).id
            return ArtifactRepository(session).list_for_project(
                project.id, feature_id=feature_id, kind=kind, latest_only=latest_only
            )

    # ------------------------------------------------------------------
    # Rendering and publishing
    # ------------------------------------------------------------------

    def render_artifact(
        self,
        artifact_id: str,
        *,
        renderer: str | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> Artifact:
        """Render a source artifact and store the output as a new artifact.

        Args:
            artifact_id: The source artifact to render.
            renderer: Renderer plugin name; defaults to the built-in
                default for the source's kind.
            options: Renderer-specific options.

        Returns:
            The derived artifact (with ``derived_from`` set).

        Raises:
            EntityNotFoundError: If the source artifact is missing.
            PluginNotFoundError: If the named renderer is not registered.
            RenderError: If rendering fails.
        """
        source, content = self.read_artifact(artifact_id)
        plugin = (
            self._renderers.get(renderer)
            if renderer is not None
            else self._renderers.default_for(source.kind)
        )
        workspace = self._workspace_dir / source.id
        workspace.mkdir(parents=True, exist_ok=True)
        result = plugin.render(
            RenderRequest(
                artifact=source,
                content=content,
                workspace=workspace,
                options=dict(options or {}),
            )
        )
        stem = source.name.rsplit(".", 1)[0]
        with self._db.session() as session:
            return self._store_artifact(
                session,
                project_id=source.project_id,
                feature_id=source.feature_id,
                task_id=source.task_id,
                kind=result.kind,
                name=f"{stem}{result.suffix}",
                content=result.content,
                media_type=result.media_type,
                metadata=dict(result.metadata),
                created_by=plugin.name,
                derived_from=source.id,
                renderer=plugin.name,
            )

    def publish_artifact(
        self,
        artifact_id: str,
        publisher: str,
        destination: str,
        *,
        options: Mapping[str, Any] | None = None,
    ) -> Publication:
        """Deliver an artifact to a destination and record the outcome.

        Failures are recorded as failed publications *and* returned (not
        raised), so callers and auditors see the full delivery history.

        Raises:
            EntityNotFoundError: If the artifact is missing.
            PluginNotFoundError: If the named publisher is not registered.
        """
        artifact, content = self.read_artifact(artifact_id)
        plugin = self._publishers.get(publisher)
        request = PublishRequest(
            artifact=artifact,
            content=content,
            destination=destination,
            options=dict(options or {}),
        )
        try:
            receipt = plugin.publish(request)
        except PublishError as exc:
            publication = Publication(
                artifact_id=artifact.id,
                publisher=plugin.name,
                destination=destination,
                status=PublicationStatus.FAILED,
                detail=str(exc),
            )
        else:
            publication = Publication(
                artifact_id=artifact.id,
                publisher=plugin.name,
                destination=destination,
                status=PublicationStatus.SUCCEEDED,
                location=receipt.location,
                detail=receipt.detail,
                metadata=dict(receipt.metadata),
            )
        with self._db.session() as session:
            return PublicationRepository(session).add(publication)

    def list_publications(self, artifact_id: str) -> Sequence[Publication]:
        """Return the delivery history of an artifact."""
        with self._db.session() as session:
            return PublicationRepository(session).list_for_artifact(artifact_id)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self, project_ref: str) -> ProjectStatusReport:
        """Summarise documentation progress for a project."""
        with self._db.session() as session:
            project = ProjectRepository(session).resolve(project_ref)
            tasks = TaskRepository(session)
            return ProjectStatusReport(
                project=project,
                features=len(FeatureRepository(session).list_for_project(project.id)),
                goals=len(GoalRepository(session).list_for_project(project.id)),
                tasks_by_status=tasks.counts_by_status(project.id),
                artifacts=ArtifactRepository(session).count_for_project(project.id),
                publications=PublicationRepository(session).count_succeeded_for_project(project.id),
                pending_task_ids=tuple(task.id for task in tasks.list_pending(project.id)),
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store_artifact(
        self,
        session: Session,
        *,
        project_id: str,
        feature_id: str | None,
        task_id: str | None,
        kind: ArtifactKind,
        name: str,
        content: bytes,
        media_type: str | None,
        metadata: dict[str, Any],
        created_by: str,
        derived_from: str | None = None,
        renderer: str | None = None,
    ) -> Artifact:
        """Write content to the blob store and its metadata to the DB."""
        if not content:
            msg = f"refusing to store empty content for artifact {name!r}"
            raise NarrateError(msg)
        content_hash, size = self._blobs.put(content)
        artifacts = ArtifactRepository(session)
        artifact = Artifact(
            project_id=project_id,
            feature_id=feature_id,
            task_id=task_id,
            kind=kind,
            name=name,
            version=artifacts.next_version(project_id, feature_id, kind, name),
            media_type=media_type or _guess_media_type(name),
            content_hash=content_hash,
            size_bytes=size,
            created_by=created_by,
            derived_from=derived_from,
            renderer=renderer,
            metadata=metadata,
        )
        return artifacts.add(artifact)


def _guess_media_type(name: str) -> str:
    """Best-effort media type from a filename."""
    guessed, _ = mimetypes.guess_type(name)
    return guessed or "application/octet-stream"


def _source_suffix(kind: ArtifactKind) -> str:
    """Default filename suffix for *source* artifacts of ``kind``."""
    if kind is ArtifactKind.MARKDOWN:
        return ".md"
    if kind is ArtifactKind.SCRIPT:
        return ".txt"
    return ".json"
