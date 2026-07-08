"""Typer application defining the ``narrate`` command."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from narrate import __version__
from narrate.container import Container
from narrate.exceptions import NarrateError
from narrate.models import ArtifactKind, PublicationStatus, TaskStatus

app = typer.Typer(
    name="narrate",
    help="AI-native documentation orchestration platform.",
    no_args_is_help=True,
)
project_app = typer.Typer(help="Manage projects.", no_args_is_help=True)
feature_app = typer.Typer(help="Manage features.", no_args_is_help=True)
goal_app = typer.Typer(help="Manage documentation goals.", no_args_is_help=True)
task_app = typer.Typer(help="Inspect and manage documentation tasks.", no_args_is_help=True)
artifact_app = typer.Typer(help="Inspect stored artifacts.", no_args_is_help=True)
plugins_app = typer.Typer(help="List renderer and publisher plugins.", no_args_is_help=True)
app.add_typer(project_app, name="project")
app.add_typer(feature_app, name="feature")
app.add_typer(goal_app, name="goal")
app.add_typer(task_app, name="task")
app.add_typer(artifact_app, name="artifact")
app.add_typer(plugins_app, name="plugins")

console = Console()


def _container() -> Container:
    """Build the standard container, translating failures to exit codes."""
    try:
        return Container()
    except NarrateError as exc:  # pragma: no cover - construction rarely fails
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _run[T](action: str, func: Callable[[], T]) -> T:
    """Execute ``func()`` and turn NarrateError into a clean CLI error."""
    try:
        return func()
    except NarrateError as exc:
        console.print(f"[red]error ({action}):[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _parse_options(options_json: str | None) -> dict[str, Any] | None:
    """Parse a ``--options`` JSON string."""
    if options_json is None:
        return None
    try:
        parsed = json.loads(options_json)
    except json.JSONDecodeError as exc:
        console.print(f"[red]error:[/red] --options is not valid JSON: {exc}")
        raise typer.Exit(code=1) from exc
    if not isinstance(parsed, dict):
        console.print("[red]error:[/red] --options must be a JSON object")
        raise typer.Exit(code=1)
    return parsed


@app.callback()
def _main() -> None:  # pyright: ignore[reportUnusedFunction] - registered by Typer
    """AI-native documentation orchestration platform."""


@app.command()
def version() -> None:
    """Print the Narrate version."""
    console.print(f"narrate {__version__}")


@app.command()
def init() -> None:
    """Initialise the Narrate home directory and database."""
    with _container() as container:
        console.print(f"home:      {container.settings.home}")
        console.print(f"database:  {container.settings.resolved_database_url}")
        console.print(f"blobs:     {container.settings.resolved_blobs_dir}")
        console.print(f"workspace: {container.settings.resolved_workspace_dir}")
        console.print("[green]Narrate is ready.[/green]")


@app.command()
def serve() -> None:
    """Run the MCP server on stdio for AI assistants."""
    from narrate.mcp.server import create_server

    with _container() as container:
        create_server(container.orchestrator).run()


@app.command()
def status(project: Annotated[str, typer.Argument(help="Project slug or id.")]) -> None:
    """Show documentation progress for a project."""
    with _container() as container:
        report = _run("status", lambda: container.orchestrator.status(project))
        console.print(f"[bold]{report.project.name}[/bold] ({report.project.slug})")
        console.print(f"features: {report.features}  goals: {report.goals}")
        counts = ", ".join(f"{k}={v}" for k, v in sorted(report.tasks_by_status.items())) or "none"
        console.print(f"tasks: {counts}")
        console.print(f"artifacts: {report.artifacts}  publications: {report.publications}")
        if report.pending_task_ids:
            console.print(f"pending task ids: {', '.join(report.pending_task_ids)}")


@app.command()
def plan(project: Annotated[str, typer.Argument(help="Project slug or id.")]) -> None:
    """Create pending tasks for every (feature, goal) pair lacking one."""
    with _container() as container:
        tasks = _run("plan", lambda: container.orchestrator.plan(project))
        if not tasks:
            console.print("Nothing to plan; all (feature, goal) pairs already have tasks.")
            return
        for task in tasks:
            console.print(f"[green]+[/green] {task.id}  {task.title}")
        console.print(f"Planned {len(tasks)} task(s).")


@app.command()
def render(
    artifact_id: Annotated[str, typer.Argument(help="Source artifact id.")],
    renderer: Annotated[str | None, typer.Option(help="Renderer name.")] = None,
    options: Annotated[str | None, typer.Option(help="Renderer options as JSON.")] = None,
) -> None:
    """Render a source artifact into a concrete output artifact."""
    with _container() as container:
        derived = _run(
            "render",
            lambda: container.orchestrator.render_artifact(
                artifact_id, renderer=renderer, options=_parse_options(options)
            ),
        )
        console.print(
            f"[green]rendered[/green] {derived.name} (v{derived.version}, "
            f"{derived.media_type}, {derived.size_bytes} bytes) -> artifact {derived.id}"
        )


@app.command()
def publish(
    artifact_id: Annotated[str, typer.Argument(help="Artifact id to publish.")],
    publisher: Annotated[str, typer.Argument(help="Publisher name.")],
    destination: Annotated[str, typer.Argument(help="Publisher destination.")],
    options: Annotated[str | None, typer.Option(help="Publisher options as JSON.")] = None,
) -> None:
    """Publish an artifact to a destination."""
    with _container() as container:
        publication = _run(
            "publish",
            lambda: container.orchestrator.publish_artifact(
                artifact_id, publisher, destination, options=_parse_options(options)
            ),
        )
        if publication.status is PublicationStatus.SUCCEEDED:
            console.print(f"[green]published[/green] -> {publication.location}")
        else:
            console.print(f"[red]publish failed:[/red] {publication.detail}")
            raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# project
# ----------------------------------------------------------------------


@project_app.command("create")
def project_create(
    name: Annotated[str, typer.Argument(help="Human readable project name.")],
    slug: Annotated[str | None, typer.Option(help="URL-safe identifier.")] = None,
    description: Annotated[str, typer.Option(help="What the product does.")] = "",
    app_url: Annotated[str | None, typer.Option(help="Running application URL.")] = None,
    repo_url: Annotated[str | None, typer.Option(help="Source repository URL.")] = None,
    tag: Annotated[list[str] | None, typer.Option(help="Repeatable label.")] = None,
) -> None:
    """Register a new project."""
    with _container() as container:
        project = _run(
            "project create",
            lambda: container.orchestrator.create_project(
                name,
                slug=slug,
                description=description,
                application_url=app_url,
                repository_url=repo_url,
                tags=tuple(tag or ()),
            ),
        )
        console.print(f"[green]created[/green] project {project.slug} ({project.id})")


@project_app.command("list")
def project_list() -> None:
    """List all projects."""
    with _container() as container:
        projects = container.orchestrator.list_projects()
        table = Table("slug", "name", "application url", "id")
        for project in projects:
            table.add_row(project.slug, project.name, project.application_url or "-", project.id)
        console.print(table)


@project_app.command("show")
def project_show(project: Annotated[str, typer.Argument(help="Project slug or id.")]) -> None:
    """Show one project with its features and goals."""
    with _container() as container:
        found = _run("project show", lambda: container.orchestrator.get_project(project))
        console.print_json(data=found.model_dump(mode="json"))
        for feature in container.orchestrator.list_features(found.id):
            console.print(f"feature: {feature.slug}  {feature.name}")
        for goal in container.orchestrator.list_goals(found.id):
            console.print(f"goal: {goal.kind.value}  audience={goal.audience}")


# ----------------------------------------------------------------------
# feature / goal
# ----------------------------------------------------------------------


@feature_app.command("add")
def feature_add(
    project: Annotated[str, typer.Argument(help="Project slug or id.")],
    name: Annotated[str, typer.Argument(help="Feature name.")],
    slug: Annotated[str | None, typer.Option(help="URL-safe identifier.")] = None,
    description: Annotated[str, typer.Option(help="What the feature does.")] = "",
    url_path: Annotated[str | None, typer.Option(help="Path in the app.")] = None,
    priority: Annotated[int, typer.Option(help="Lower renders first.")] = 100,
) -> None:
    """Register a feature on a project."""
    with _container() as container:
        feature = _run(
            "feature add",
            lambda: container.orchestrator.add_feature(
                project,
                name,
                slug=slug,
                description=description,
                url_path=url_path,
                priority=priority,
            ),
        )
        console.print(f"[green]added[/green] feature {feature.slug} ({feature.id})")


@goal_app.command("add")
def goal_add(
    project: Annotated[str, typer.Argument(help="Project slug or id.")],
    kind: Annotated[ArtifactKind, typer.Argument(help="Artifact kind to produce.")],
    audience: Annotated[str, typer.Option(help="Who it is for.")] = "end users",
    tone: Annotated[str, typer.Option(help="Editorial voice.")] = "clear and friendly",
    instructions: Annotated[str, typer.Option(help="Standing guidance.")] = "",
) -> None:
    """Add a documentation goal (desired artifact kind) to a project."""
    with _container() as container:
        goal = _run(
            "goal add",
            lambda: container.orchestrator.add_goal(
                project, kind, audience=audience, tone=tone, instructions=instructions
            ),
        )
        console.print(f"[green]added[/green] goal {goal.kind.value} ({goal.id})")


@goal_app.command("list")
def goal_list(project: Annotated[str, typer.Argument(help="Project slug or id.")]) -> None:
    """List a project's documentation goals."""
    with _container() as container:
        goals = _run("goal list", lambda: container.orchestrator.list_goals(project))
        table = Table("kind", "audience", "tone", "id")
        for goal in goals:
            table.add_row(goal.kind.value, goal.audience, goal.tone, goal.id)
        console.print(table)


# ----------------------------------------------------------------------
# task
# ----------------------------------------------------------------------


@task_app.command("list")
def task_list(
    project: Annotated[str, typer.Argument(help="Project slug or id.")],
    status: Annotated[TaskStatus | None, typer.Option(help="Filter by status.")] = None,
) -> None:
    """List a project's tasks."""
    with _container() as container:
        tasks = _run("task list", lambda: container.orchestrator.list_tasks(project, status=status))
        table = Table("id", "status", "kind", "title", "claimed by")
        for task in tasks:
            table.add_row(
                task.id, task.status.value, task.kind.value, task.title, task.claimed_by or "-"
            )
        console.print(table)


@task_app.command("show")
def task_show(task_id: Annotated[str, typer.Argument(help="Task id.")]) -> None:
    """Show one task including its full agent instructions."""
    with _container() as container:
        task = _run("task show", lambda: container.orchestrator.get_task(task_id))
        console.print_json(data=task.model_dump(mode="json"))


@task_app.command("cancel")
def task_cancel(task_id: Annotated[str, typer.Argument(help="Task id.")]) -> None:
    """Withdraw a pending or in-progress task."""
    with _container() as container:
        task = _run("task cancel", lambda: container.orchestrator.cancel_task(task_id))
        console.print(f"[yellow]cancelled[/yellow] task {task.id}")


# ----------------------------------------------------------------------
# artifact
# ----------------------------------------------------------------------


@artifact_app.command("list")
def artifact_list(
    project: Annotated[str, typer.Argument(help="Project slug or id.")],
    feature: Annotated[str | None, typer.Option(help="Filter by feature slug.")] = None,
    kind: Annotated[ArtifactKind | None, typer.Option(help="Filter by kind.")] = None,
    latest_only: Annotated[bool, typer.Option(help="Newest version only.")] = False,
) -> None:
    """List a project's stored artifacts."""
    with _container() as container:
        artifacts = _run(
            "artifact list",
            lambda: container.orchestrator.list_artifacts(
                project, feature_ref=feature, kind=kind, latest_only=latest_only
            ),
        )
        table = Table("id", "kind", "name", "version", "size", "renderer")
        for artifact in artifacts:
            table.add_row(
                artifact.id,
                artifact.kind.value,
                artifact.name,
                str(artifact.version),
                str(artifact.size_bytes),
                artifact.renderer or "-",
            )
        console.print(table)


@artifact_app.command("export")
def artifact_export(
    artifact_id: Annotated[str, typer.Argument(help="Artifact id.")],
    path: Annotated[Path, typer.Argument(help="Destination file path.")],
) -> None:
    """Write an artifact's content to a local file."""
    with _container() as container:
        artifact, content = _run(
            "artifact export", lambda: container.orchestrator.read_artifact(artifact_id)
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        console.print(f"[green]exported[/green] {artifact.name} -> {path} ({len(content)} bytes)")


# ----------------------------------------------------------------------
# plugins
# ----------------------------------------------------------------------


@plugins_app.command("list")
def plugins_list() -> None:
    """List available renderer and publisher plugins."""
    with _container() as container:
        renderers = Table("renderer", "inputs", "output", "description")
        for renderer in container.renderers.all():
            renderers.add_row(
                renderer.name,
                ", ".join(sorted(kind.value for kind in renderer.input_kinds)),
                renderer.output_kind.value,
                renderer.description,
            )
        console.print(renderers)
        publishers = Table("publisher", "description")
        for publisher in container.publishers.all():
            publishers.add_row(publisher.name, publisher.description)
        console.print(publishers)


if __name__ == "__main__":  # pragma: no cover
    app()
