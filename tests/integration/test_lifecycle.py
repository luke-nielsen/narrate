"""End-to-end lifecycle: describe -> plan -> generate -> render -> publish."""

import json
from pathlib import Path

import pytest

from narrate.config import NarrateSettings
from narrate.container import Container
from narrate.models import ArtifactKind, TaskStatus

pytestmark = pytest.mark.integration

DECK = {
    "title": "Shared notebooks",
    "subtitle": "Collaborate in Acme Notes",
    "slides": [{"title": "Invite teammates", "bullets": ["Open a notebook", "Click share"]}],
}


def test_full_documentation_lifecycle(container: Container, tmp_path: Path):
    engine = container.orchestrator

    # 1. Describe the product.
    project = engine.create_project(
        "Acme Notes",
        description="A collaborative note-taking app",
        application_url="https://notes.acme.test",
    )
    engine.add_feature(project.slug, "Shared notebooks", url_path="/notebooks")
    engine.add_goal(project.slug, ArtifactKind.MARKDOWN)
    engine.add_goal(project.slug, ArtifactKind.SLIDE_DECK)

    # 2. Plan: one task per (feature, goal).
    tasks = engine.plan(project.slug)
    assert {t.kind for t in tasks} == {ArtifactKind.MARKDOWN, ArtifactKind.SLIDE_DECK}

    # 3. An "agent" works both tasks.
    site = tmp_path / "site"
    for task in tasks:
        claimed = engine.claim_task(task.id, agent="integration-agent")
        assert "Acme Notes" in claimed.instructions
        if task.kind is ArtifactKind.MARKDOWN:
            payload = b"# Shared notebooks\n\nInvite teammates to collaborate."
        else:
            payload = json.dumps(DECK).encode()
        source = engine.save_task_artifact(claimed.id, payload)

        # 4. Render and publish the output.
        derived = engine.render_artifact(source.id)
        publication = engine.publish_artifact(derived.id, "static_site", str(site))
        assert publication.status.value == "succeeded"
        engine.complete_task(claimed.id)

    # 5. The published site lists both artifacts and progress is complete.
    manifest = json.loads((site / "manifest.json").read_text())
    assert len(manifest) == 2
    assert (site / "index.html").exists()

    report = engine.status(project.slug)
    assert report.tasks_by_status == {TaskStatus.COMPLETED.value: 2}
    assert report.artifacts == 4  # 2 sources + 2 rendered
    assert report.publications == 2
    assert report.pending_task_ids == ()


def test_state_survives_container_restart(settings: NarrateSettings, tmp_path: Path):
    with Container(settings) as first:
        project = first.orchestrator.create_project("Persistent App")
        first.orchestrator.add_feature(project.slug, "Login")
        first.orchestrator.add_goal(project.slug, ArtifactKind.MARKDOWN)
        first.orchestrator.plan(project.slug)

    with Container(settings) as second:
        engine = second.orchestrator
        pending = engine.list_pending_tasks("persistent-app")
        assert len(pending) == 1
        claimed = engine.claim_task(pending[0].id, agent="second-life")
        artifact = engine.save_task_artifact(claimed.id, b"# Login guide")

    with Container(settings) as third:
        loaded, content = third.orchestrator.read_artifact(artifact.id)
        assert content == b"# Login guide"
        assert loaded.created_by == "second-life"
