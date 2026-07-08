"""Tests for the orchestration engine's lifecycle rules."""

from pathlib import Path

import pytest

from narrate.exceptions import (
    EntityNotFoundError,
    InvalidTransitionError,
    NarrateError,
    PublishError,
)
from narrate.models import (
    ArtifactKind,
    DocumentationTask,
    Project,
    PublicationStatus,
    TaskStatus,
)
from narrate.orchestration.engine import Orchestrator
from narrate.publishing.base import Publisher, PublishReceipt, PublishRequest


def test_create_project_derives_slug(engine: Orchestrator):
    project = engine.create_project("My Cool App")
    assert project.slug == "my-cool-app"


def test_plan_is_idempotent(engine: Orchestrator, project: Project):
    first = engine.plan(project.slug)
    assert len(first) == 4  # 2 features x 2 goals
    assert engine.plan(project.slug) == []


def test_claim_requires_pending(engine: Orchestrator, claimed_task: DocumentationTask):
    with pytest.raises(InvalidTransitionError, match="only pending"):
        engine.claim_task(claimed_task.id, agent="someone-else")


def test_save_requires_claim(engine: Orchestrator, project: Project):
    tasks = engine.plan(project.slug)
    with pytest.raises(InvalidTransitionError, match="claim it"):
        engine.save_task_artifact(tasks[0].id, b"content")


def test_complete_requires_artifact(engine: Orchestrator, claimed_task: DocumentationTask):
    with pytest.raises(InvalidTransitionError, match="no saved artifact"):
        engine.complete_task(claimed_task.id)


def test_full_task_lifecycle(engine: Orchestrator, claimed_task: DocumentationTask):
    artifact = engine.save_task_artifact(
        claimed_task.id, b"# Guide\n\nUse it.", metadata={"title": "Guide"}
    )
    assert artifact.task_id == claimed_task.id
    assert artifact.created_by == "test-agent"
    completed = engine.complete_task(claimed_task.id)
    assert completed.status is TaskStatus.COMPLETED
    assert completed.artifact_id == artifact.id


def test_resave_creates_new_version_and_repoints_task(
    engine: Orchestrator, claimed_task: DocumentationTask
):
    first = engine.save_task_artifact(claimed_task.id, b"v1")
    second = engine.save_task_artifact(claimed_task.id, b"v2")
    assert (first.version, second.version) == (1, 2)
    assert engine.get_task(claimed_task.id).artifact_id == second.id


def test_fail_and_cancel_are_terminal(engine: Orchestrator, project: Project):
    tasks = engine.plan(project.slug)
    failed = engine.fail_task(tasks[0].id, "no access to the app")
    assert failed.status is TaskStatus.FAILED
    assert failed.error == "no access to the app"
    with pytest.raises(InvalidTransitionError):
        engine.fail_task(tasks[0].id, "again")
    cancelled = engine.cancel_task(tasks[1].id)
    assert cancelled.status is TaskStatus.CANCELLED
    with pytest.raises(InvalidTransitionError):
        engine.claim_task(tasks[1].id)


def test_empty_content_rejected(engine: Orchestrator, claimed_task: DocumentationTask):
    with pytest.raises(NarrateError, match="empty content"):
        engine.save_task_artifact(claimed_task.id, b"")


def test_read_artifact_roundtrip(engine: Orchestrator, claimed_task: DocumentationTask):
    saved = engine.save_task_artifact(claimed_task.id, b"payload")
    artifact, content = engine.read_artifact(saved.id)
    assert content == b"payload"
    assert artifact.content_hash == saved.content_hash


def test_standalone_artifact_with_feature_scope(engine: Orchestrator, project: Project):
    artifact = engine.save_artifact(
        project.slug,
        ArtifactKind.MARKDOWN,
        "changelog.md",
        b"# Changelog",
        feature_ref="shared-notebooks",
        created_by="human",
    )
    assert artifact.feature_id is not None
    assert artifact.created_by == "human"
    listed = engine.list_artifacts(project.slug, feature_ref="shared-notebooks")
    assert [a.id for a in listed] == [artifact.id]


def test_render_uses_default_renderer_and_links_provenance(
    engine: Orchestrator, claimed_task: DocumentationTask
):
    source = engine.save_task_artifact(claimed_task.id, b"# Guide\n\nStep one.")
    derived = engine.render_artifact(source.id)
    assert derived.derived_from == source.id
    assert derived.renderer == "markdown"
    assert derived.media_type == "text/markdown"
    _, content = engine.read_artifact(derived.id)
    assert b"artifact_id: " + source.id.encode() in content


def test_render_unknown_artifact(engine: Orchestrator):
    with pytest.raises(EntityNotFoundError):
        engine.render_artifact("missing")


def test_publish_records_success(
    engine: Orchestrator, claimed_task: DocumentationTask, tmp_path: Path
):
    source = engine.save_task_artifact(claimed_task.id, b"# Guide")
    publication = engine.publish_artifact(source.id, "filesystem", str(tmp_path / "out"))
    assert publication.status is PublicationStatus.SUCCEEDED
    assert publication.location is not None
    assert [p.id for p in engine.list_publications(source.id)] == [publication.id]


class ExplodingPublisher(Publisher):
    name = "exploding"
    description = "always fails"

    def publish(self, request: PublishRequest) -> PublishReceipt:
        raise PublishError("destination on fire")


def test_publish_failure_is_recorded_not_raised(
    engine: Orchestrator, claimed_task: DocumentationTask
):
    engine.publishers.register(ExplodingPublisher())
    source = engine.save_task_artifact(claimed_task.id, b"# Guide")
    publication = engine.publish_artifact(source.id, "exploding", "anywhere")
    assert publication.status is PublicationStatus.FAILED
    assert publication.detail is not None and "on fire" in publication.detail
    assert engine.status(claimed_task.project_id).publications == 0  # only successes count


def test_status_report_aggregates(engine: Orchestrator, project: Project):
    tasks = engine.plan(project.slug)
    claimed = engine.claim_task(tasks[0].id, agent="a")
    engine.save_task_artifact(claimed.id, b"# Doc")
    engine.complete_task(claimed.id)
    report = engine.status(project.slug)
    assert report.features == 2
    assert report.goals == 2
    assert report.tasks_by_status == {"pending": 3, "completed": 1}
    assert report.artifacts == 1
    assert set(report.pending_task_ids) == {t.id for t in tasks[1:]}
