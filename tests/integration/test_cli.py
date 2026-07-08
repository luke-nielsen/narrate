"""Integration tests for the Typer CLI."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from narrate.cli.main import app

pytestmark = pytest.mark.integration

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every CLI invocation at a temp Narrate home."""
    home = tmp_path / "cli-home"
    monkeypatch.setenv("NARRATE_HOME", str(home))
    monkeypatch.chdir(tmp_path)  # keep any stray .env out of scope
    return home


def invoke(*args: str, expect_exit: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == expect_exit, result.output
    return result.output


def test_version_and_init():
    assert "narrate" in invoke("version")
    output = invoke("init")
    assert "Narrate is ready" in output


def test_end_to_end_via_cli(tmp_path: Path):
    invoke(
        "project",
        "create",
        "Acme Notes",
        "--description",
        "Note taking",
        "--app-url",
        "https://notes.acme.test",
        "--tag",
        "saas",
    )
    assert "acme-notes" in invoke("project", "list")

    invoke("feature", "add", "acme-notes", "Shared notebooks", "--url-path", "/notebooks")
    invoke("goal", "add", "acme-notes", "markdown")
    invoke("goal", "add", "acme-notes", "slide_deck")
    assert "markdown" in invoke("goal", "list", "acme-notes")

    plan_output = invoke("plan", "acme-notes")
    assert "Planned 2 task(s)." in plan_output
    assert "Nothing to plan" in invoke("plan", "acme-notes")  # idempotent

    task_table = invoke("task", "list", "acme-notes")
    assert "pending" in task_table

    status_output = invoke("status", "acme-notes")
    assert "pending=2" in status_output


def test_render_publish_export_via_cli(tmp_path: Path):
    invoke("project", "create", "Acme")
    invoke("feature", "add", "acme", "Login")
    invoke("goal", "add", "acme", "markdown")
    invoke("plan", "acme")

    # Complete the agent part through the engine (the CLI is the human side).
    from narrate.container import Container

    with Container() as container:
        engine = container.orchestrator
        task = engine.list_pending_tasks("acme")[0]
        engine.claim_task(task.id, agent="cli-test")
        source = engine.save_task_artifact(task.id, b"# Login\n\nSign in with SSO.")

    render_output = invoke("render", source.id)
    assert "rendered" in render_output

    with Container() as container:
        derived = container.orchestrator.list_artifacts("acme", latest_only=True)
        rendered = next(a for a in derived if a.renderer == "markdown")

    out_dir = tmp_path / "published"
    publish_output = invoke("publish", rendered.id, "filesystem", str(out_dir))
    assert "published" in publish_output
    assert any(out_dir.iterdir())

    export_path = tmp_path / "export" / "login.md"
    invoke("artifact", "export", rendered.id, str(export_path))
    assert export_path.read_text().startswith("---")

    listing = invoke("artifact", "list", "acme")
    assert "markdown" in listing


def test_task_show_outputs_json():
    invoke("project", "create", "Acme")
    invoke("feature", "add", "acme", "Login")
    invoke("goal", "add", "acme", "markdown")
    invoke("plan", "acme")
    from narrate.container import Container

    with Container() as container:
        task = container.orchestrator.list_pending_tasks("acme")[0]
    output = invoke("task", "show", task.id)
    parsed = json.loads(output)
    assert parsed["status"] == "pending"


def test_unknown_project_exits_nonzero():
    output = invoke("status", "ghost", expect_exit=1)
    assert "not found" in output


def test_bad_options_json_rejected():
    invoke("project", "create", "Acme")
    output = invoke("render", "whatever", "--options", "{bad", expect_exit=1)
    assert "not valid JSON" in output
