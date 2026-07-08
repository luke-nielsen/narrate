"""Tests for the pure task planner."""

from narrate.models import ArtifactKind, DocumentationGoal, Feature, Project
from narrate.orchestration.planner import TaskPlanner


def _fixtures() -> tuple[Project, list[Feature], list[DocumentationGoal]]:
    project = Project(
        slug="acme",
        name="Acme",
        description="An app",
        application_url="https://acme.test",
    )
    features = [
        Feature(project_id=project.id, slug="search", name="Search", priority=2),
        Feature(project_id=project.id, slug="auth", name="Auth", priority=1, url_path="/login"),
    ]
    goals = [
        DocumentationGoal(project_id=project.id, kind=ArtifactKind.MARKDOWN),
        DocumentationGoal(
            project_id=project.id, kind=ArtifactKind.VIDEO, instructions="Keep it short."
        ),
    ]
    return project, features, goals


def test_plan_expands_feature_goal_matrix():
    project, features, goals = _fixtures()
    tasks = TaskPlanner().plan(project, features, goals, existing=[])
    assert len(tasks) == 4
    # ordered by feature priority (auth first), then kind
    assert [(t.feature_id, t.kind) for t in tasks[:2]] == [
        (features[1].id, ArtifactKind.MARKDOWN),
        (features[1].id, ArtifactKind.VIDEO),
    ]


def test_plan_skips_existing_pairs():
    project, features, goals = _fixtures()
    planner = TaskPlanner()
    first = planner.plan(project, features, goals, existing=[])
    existing = [(t.feature_id, t.goal_id) for t in first]
    assert planner.plan(project, features, goals, existing=existing) == []


def test_instructions_carry_full_context():
    project, features, goals = _fixtures()
    text = TaskPlanner.build_instructions(project, features[1], goals[1])
    assert "Acme" in text
    assert "https://acme.test" in text
    assert "/login" in text
    assert "Keep it short." in text
    assert "duration_seconds" in text  # the video format hint


def test_titles_are_readable():
    project, features, goals = _fixtures()
    tasks = TaskPlanner().plan(project, features, goals, existing=[])
    assert tasks[0].title == "Markdown: Auth"
