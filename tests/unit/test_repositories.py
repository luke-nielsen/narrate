"""Tests for the repository layer."""

import pytest

from narrate.container import Container
from narrate.exceptions import DuplicateEntityError, EntityNotFoundError
from narrate.models import (
    Artifact,
    ArtifactKind,
    DocumentationTask,
    Feature,
    Project,
    TaskStatus,
)
from narrate.storage.repositories import (
    ArtifactRepository,
    FeatureRepository,
    ProjectRepository,
    TaskRepository,
)


def test_project_roundtrip_preserves_fields(container: Container):
    project = Project(
        slug="acme",
        name="Acme",
        description="desc",
        application_url="https://acme.test",
        repository_url="https://github.com/acme/acme",
        tags=("a", "b"),
    )
    with container.database.session() as session:
        ProjectRepository(session).add(project)
    with container.database.session() as session:
        loaded = ProjectRepository(session).get(project.id)
    assert loaded == project
    assert loaded.created_at.tzinfo is not None


def test_project_duplicate_slug_rejected(container: Container):
    with container.database.session() as session:
        repo = ProjectRepository(session)
        repo.add(Project(slug="acme", name="Acme"))
        with pytest.raises(DuplicateEntityError):
            repo.add(Project(slug="acme", name="Other"))


def test_project_resolve_by_id_or_slug(container: Container):
    project = Project(slug="acme", name="Acme")
    with container.database.session() as session:
        ProjectRepository(session).add(project)
    with container.database.session() as session:
        repo = ProjectRepository(session)
        assert repo.resolve(project.id).id == project.id
        assert repo.resolve("acme").id == project.id
        with pytest.raises(EntityNotFoundError):
            repo.resolve("nope")


def test_feature_unique_per_project_only(container: Container):
    first = Project(slug="one", name="One")
    second = Project(slug="two", name="Two")
    with container.database.session() as session:
        ProjectRepository(session).add(first)
        ProjectRepository(session).add(second)
        features = FeatureRepository(session)
        features.add(Feature(project_id=first.id, slug="search", name="Search"))
        features.add(Feature(project_id=second.id, slug="search", name="Search"))
        with pytest.raises(DuplicateEntityError):
            features.add(Feature(project_id=first.id, slug="search", name="Again"))


def test_task_partial_update_bumps_updated_at(
    container: Container, claimed_task: DocumentationTask
):
    with container.database.session() as session:
        repo = TaskRepository(session)
        before = repo.get(claimed_task.id)
        updated = repo.update(claimed_task.id, error="boom")
    assert updated.error == "boom"
    assert updated.status == before.status  # untouched fields survive
    assert updated.updated_at >= before.updated_at


def test_task_counts_by_status(container: Container, project: Project):
    engine = container.orchestrator
    tasks = engine.plan(project.slug)
    engine.claim_task(tasks[0].id, agent="a")
    with container.database.session() as session:
        counts = TaskRepository(session).counts_by_status(project.id)
    assert counts[TaskStatus.PENDING.value] == len(tasks) - 1
    assert counts[TaskStatus.IN_PROGRESS.value] == 1


def _artifact(project_id: str, name: str = "a.md", version: int = 1) -> Artifact:
    return Artifact(
        project_id=project_id,
        kind=ArtifactKind.MARKDOWN,
        name=name,
        version=version,
        content_hash="0" * 64,
        size_bytes=1,
    )


def test_artifact_versioning(container: Container, project: Project):
    with container.database.session() as session:
        repo = ArtifactRepository(session)
        assert repo.next_version(project.id, None, ArtifactKind.MARKDOWN, "a.md") == 1
        repo.add(_artifact(project.id))
        assert repo.next_version(project.id, None, ArtifactKind.MARKDOWN, "a.md") == 2
        # different name has its own version sequence
        assert repo.next_version(project.id, None, ArtifactKind.MARKDOWN, "b.md") == 1


def test_artifact_latest_only_filter(container: Container, project: Project):
    with container.database.session() as session:
        repo = ArtifactRepository(session)
        repo.add(_artifact(project.id, version=1))
        repo.add(_artifact(project.id, version=2))
        repo.add(_artifact(project.id, name="b.md", version=1))
        latest = repo.list_for_project(project.id, latest_only=True)
    assert {(a.name, a.version) for a in latest} == {("a.md", 2), ("b.md", 1)}
