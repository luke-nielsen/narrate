"""Shared fixtures: every test gets an isolated Narrate installation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from narrate.config import NarrateSettings
from narrate.container import Container
from narrate.models import ArtifactKind, DocumentationTask, Project
from narrate.orchestration.engine import Orchestrator


@pytest.fixture
def settings(tmp_path: Path) -> NarrateSettings:
    """Settings rooted in a temporary directory, ignoring the environment."""
    return NarrateSettings(home=tmp_path / "narrate-home", _env_file=None)  # pyright: ignore[reportCallIssue]


@pytest.fixture
def container(settings: NarrateSettings) -> Iterator[Container]:
    """A fully wired container against a temp SQLite DB and blob store."""
    with Container(settings) as built:
        yield built


@pytest.fixture
def engine(container: Container) -> Orchestrator:
    """The orchestration engine from the wired container."""
    return container.orchestrator


@pytest.fixture
def project(engine: Orchestrator) -> Project:
    """A project with two features and two goals, ready for planning."""
    created = engine.create_project(
        "Acme Notes",
        slug="acme-notes",
        description="A collaborative note-taking app",
        application_url="https://notes.acme.test",
        tags=("saas", "notes"),
    )
    engine.add_feature(
        created.slug,
        "Shared notebooks",
        description="Create notebooks and invite teammates",
        url_path="/notebooks",
        priority=1,
    )
    engine.add_feature(
        created.slug,
        "Full-text search",
        description="Search across all notes instantly",
        url_path="/search",
        priority=2,
    )
    engine.add_goal(created.slug, ArtifactKind.MARKDOWN)
    engine.add_goal(created.slug, ArtifactKind.SLIDE_DECK, audience="new customers")
    return created


@pytest.fixture
def claimed_task(engine: Orchestrator, project: Project) -> DocumentationTask:
    """The first planned task, already claimed by ``test-agent``."""
    tasks = engine.plan(project.slug)
    return engine.claim_task(tasks[0].id, agent="test-agent")
