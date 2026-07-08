"""Core domain entities.

All entities are frozen Pydantic models: mutation happens exclusively in
the storage layer, which returns fresh instances.  Timestamps are always
timezone-aware UTC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from narrate.models.enums import ArtifactKind, PublicationStatus, TaskStatus
from narrate.models.support import new_id, utcnow

__all__ = [
    "Artifact",
    "DocumentationGoal",
    "DocumentationTask",
    "Feature",
    "Project",
    "ProjectStatusReport",
    "Publication",
]


class _Entity(BaseModel):
    """Base class configuring shared model behaviour."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utcnow)


class Project(_Entity):
    """A software product whose documentation Narrate orchestrates.

    Attributes:
        slug: Unique, URL-safe identifier chosen by the user.
        name: Human readable project name.
        description: What the product does; given to AI agents as context.
        application_url: URL of the running application being documented.
        repository_url: Optional source repository URL.
        tags: Free-form labels for filtering and discovery.
    """

    slug: str
    name: str
    description: str = ""
    application_url: str | None = None
    repository_url: str | None = None
    tags: tuple[str, ...] = ()


class Feature(_Entity):
    """A discrete capability of a project that deserves documentation.

    Attributes:
        project_id: Owning :class:`Project` identifier.
        slug: Unique (per project) URL-safe identifier.
        name: Human readable feature name.
        description: What the feature does and why it matters.
        url_path: Path within the application where the feature lives.
        priority: Lower numbers are planned first.
    """

    project_id: str
    slug: str
    name: str
    description: str = ""
    url_path: str | None = None
    priority: int = 100


class DocumentationGoal(_Entity):
    """A desired artifact kind for a project's features.

    A goal says "every feature of this project should have a *video*" (or
    markdown page, slide deck, ...).  The planner expands goals against
    features to produce concrete :class:`DocumentationTask` rows.

    Attributes:
        project_id: Owning project identifier.
        kind: The artifact kind this goal requires.
        audience: Who the artifact is for (e.g. ``"end users"``).
        tone: Editorial voice, e.g. ``"friendly"`` or ``"reference"``.
        instructions: Additional standing guidance for AI agents.
    """

    project_id: str
    kind: ArtifactKind
    audience: str = "end users"
    tone: str = "clear and friendly"
    instructions: str = ""


class DocumentationTask(_Entity):
    """One unit of documentation work for an AI agent.

    Tasks pair a feature with a goal kind.  Agents claim a task, generate
    content, save it as an artifact, optionally render and publish it, and
    finally mark the task completed.

    Attributes:
        project_id: Owning project identifier.
        feature_id: The feature to document.
        goal_id: The goal that spawned this task.
        kind: Artifact kind the agent must produce.
        title: Short human readable summary of the work.
        instructions: Merged goal + feature context handed to the agent.
        status: Current lifecycle state.
        claimed_by: Name of the agent that claimed the task, if any.
        artifact_id: The accepted artifact once one has been saved.
        error: Failure detail when :attr:`status` is ``FAILED``.
        updated_at: Last state change.
    """

    project_id: str
    feature_id: str
    goal_id: str
    kind: ArtifactKind
    title: str
    instructions: str = ""
    status: TaskStatus = TaskStatus.PENDING
    claimed_by: str | None = None
    artifact_id: str | None = None
    error: str | None = None
    updated_at: datetime = Field(default_factory=utcnow)


class Artifact(_Entity):
    """A stored documentation artifact plus its metadata.

    Artifact *content* lives in the content-addressed blob store; this
    model records everything needed to version, regenerate, reuse, and
    publish it.  Derived artifacts (renderer outputs) point back at their
    source via :attr:`derived_from`.

    Attributes:
        project_id: Owning project identifier.
        feature_id: Feature the artifact documents, if feature-scoped.
        task_id: Task that produced the artifact, if any.
        kind: What the artifact is.
        name: Filename-ish label, e.g. ``"getting-started.md"``.
        version: Monotonic version per (project, feature, kind, name).
        media_type: IANA media type of the stored content.
        content_hash: SHA-256 of the content in the blob store.
        size_bytes: Content length in bytes.
        created_by: Agent or user attribution.
        derived_from: Source artifact id when produced by a renderer.
        renderer: Renderer plugin name for derived artifacts.
        metadata: Arbitrary JSON-serialisable annotations.
    """

    project_id: str
    feature_id: str | None = None
    task_id: str | None = None
    kind: ArtifactKind
    name: str
    version: int = 1
    media_type: str = "text/plain"
    content_hash: str
    size_bytes: int
    created_by: str = "unknown"
    derived_from: str | None = None
    renderer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Publication(_Entity):
    """A record of an artifact being delivered to a destination.

    Attributes:
        artifact_id: The published artifact.
        publisher: Publisher plugin name.
        destination: Publisher-specific destination string.
        status: Whether delivery succeeded.
        location: Where the content ended up (URL or path), if known.
        detail: Error message or publisher-provided notes.
        metadata: Arbitrary JSON-serialisable annotations.
    """

    artifact_id: str
    publisher: str
    destination: str
    status: PublicationStatus
    location: str | None = None
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectStatusReport(BaseModel):
    """Aggregate documentation progress for one project.

    Attributes:
        project: The project being summarised.
        features: Number of features registered.
        goals: Number of documentation goals configured.
        tasks_by_status: Task counts keyed by status value.
        artifacts: Total stored artifacts (all versions).
        publications: Total successful publications.
        pending_task_ids: Identifiers of tasks awaiting an agent.
    """

    model_config = ConfigDict(frozen=True)

    project: Project
    features: int
    goals: int
    tasks_by_status: dict[str, int]
    artifacts: int
    publications: int
    pending_task_ids: tuple[str, ...] = ()
