# pyright: reportUnusedFunction=false
# (tool functions are registered via the @mcp.tool decorator, not called directly)
"""The Narrate MCP server.

Exposes the documentation lifecycle as deterministic MCP tools so AI
assistants can discover pending work and produce documentation one tool
call at a time:

1. ``list_projects`` / ``get_documentation_status`` -- discover work.
2. ``list_pending_tasks`` -> ``claim_task`` -- pick up a task.
3. ``save_artifact`` -- store generated content (the task's instructions
   say exactly what format each artifact kind expects).
4. ``render_artifact`` -- turn the source into concrete outputs.
5. ``publish_artifact`` -- deliver outputs to destinations.
6. ``complete_task`` -- mark the work done.

Run it with ``narrate serve`` (stdio transport) and register it with any
MCP-capable assistant.
"""

from __future__ import annotations

import base64
import binascii
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP

from narrate.container import Container
from narrate.exceptions import NarrateError
from narrate.models import (
    Artifact,
    ArtifactKind,
    DocumentationTask,
    Project,
    Publication,
    TaskStatus,
)

if TYPE_CHECKING:
    from narrate.orchestration.engine import Orchestrator

__all__ = ["create_server"]

_TEXT_PREVIEW_LIMIT = 100_000


def _project_dict(project: Project) -> dict[str, Any]:
    """Serialise a project for tool output."""
    return project.model_dump(mode="json")


def _task_dict(task: DocumentationTask) -> dict[str, Any]:
    """Serialise a task for tool output."""
    return task.model_dump(mode="json")


def _artifact_dict(artifact: Artifact) -> dict[str, Any]:
    """Serialise an artifact for tool output."""
    return artifact.model_dump(mode="json")


def _publication_dict(publication: Publication) -> dict[str, Any]:
    """Serialise a publication for tool output."""
    return publication.model_dump(mode="json")


def _decode_content(content: str, encoding: str) -> bytes:
    """Decode tool-supplied content to bytes.

    Args:
        content: The payload.
        encoding: ``"text"`` for UTF-8 text or ``"base64"`` for binary.

    Raises:
        NarrateError: If the encoding is unknown or base64 is invalid.
    """
    if encoding == "text":
        return content.encode("utf-8")
    if encoding == "base64":
        try:
            return base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError) as exc:
            msg = f"content is not valid base64: {exc}"
            raise NarrateError(msg) from exc
    msg = f"unknown encoding {encoding!r} (use 'text' or 'base64')"
    raise NarrateError(msg)


def create_server(orchestrator: Orchestrator | None = None) -> FastMCP:
    """Build the Narrate MCP server.

    Args:
        orchestrator: Injected engine; when omitted a standard
            :class:`~narrate.container.Container` is built from the
            environment.

    Returns:
        A configured FastMCP server (run with ``.run()``).
    """
    engine = orchestrator if orchestrator is not None else Container().orchestrator
    mcp = FastMCP(
        "narrate",
        instructions=(
            "Narrate orchestrates documentation work for software products. "
            "Discover projects and pending documentation tasks, claim a task, "
            "save the artifact you generate (the task instructions describe "
            "the exact format), then render, publish, and complete it."
        ),
    )

    # -- discovery ------------------------------------------------------

    @mcp.tool()
    def list_projects() -> list[dict[str, Any]]:
        """List all projects whose documentation Narrate orchestrates."""
        return [_project_dict(project) for project in engine.list_projects()]

    @mcp.tool()
    def get_project(project: str) -> dict[str, Any]:
        """Get one project by slug or id, including its features and goals.

        Args:
            project: Project slug or id.
        """
        found = engine.get_project(project)
        return {
            **_project_dict(found),
            "features": [f.model_dump(mode="json") for f in engine.list_features(found.id)],
            "goals": [g.model_dump(mode="json") for g in engine.list_goals(found.id)],
        }

    @mcp.tool()
    def get_documentation_status(project: str) -> dict[str, Any]:
        """Summarise documentation progress for a project.

        Args:
            project: Project slug or id.
        """
        return engine.status(project).model_dump(mode="json")

    # -- task lifecycle ---------------------------------------------------

    @mcp.tool()
    def plan_documentation(project: str) -> list[dict[str, Any]]:
        """Create pending tasks for every (feature, goal) pair lacking one.

        Planning is idempotent; only newly created tasks are returned.

        Args:
            project: Project slug or id.
        """
        return [_task_dict(task) for task in engine.plan(project)]

    @mcp.tool()
    def list_pending_tasks(project: str | None = None) -> list[dict[str, Any]]:
        """List documentation tasks waiting for an agent.

        Args:
            project: Optional project slug or id to filter by; omit to
                see pending work across all projects.
        """
        return [_task_dict(task) for task in engine.list_pending_tasks(project)]

    @mcp.tool()
    def get_task(task_id: str) -> dict[str, Any]:
        """Get one documentation task, including its full instructions.

        Args:
            task_id: The task id.
        """
        return _task_dict(engine.get_task(task_id))

    @mcp.tool()
    def claim_task(task_id: str, agent_name: str | None = None) -> dict[str, Any]:
        """Claim a pending task before working on it.

        Args:
            task_id: The task to claim.
            agent_name: How you want to be attributed on the work.
        """
        return _task_dict(engine.claim_task(task_id, agent=agent_name))

    @mcp.tool()
    def complete_task(task_id: str) -> dict[str, Any]:
        """Mark a claimed task as completed (requires a saved artifact).

        Args:
            task_id: The task to complete.
        """
        return _task_dict(engine.complete_task(task_id))

    @mcp.tool()
    def fail_task(task_id: str, reason: str) -> dict[str, Any]:
        """Mark a task as failed with a reason so a human can intervene.

        Args:
            task_id: The task that cannot be finished.
            reason: What went wrong.
        """
        return _task_dict(engine.fail_task(task_id, reason))

    # -- artifacts --------------------------------------------------------

    @mcp.tool()
    def save_artifact(
        task_id: str,
        content: str,
        name: str | None = None,
        media_type: str | None = None,
        encoding: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save generated content as the artifact for a claimed task.

        The task's instructions describe the exact format expected for its
        artifact kind.  Saving again creates a new version.

        Args:
            task_id: The claimed task this content fulfils.
            content: The artifact payload.
            name: Optional filename (a sensible default is derived).
            media_type: Optional IANA media type.
            encoding: 'text' for UTF-8 content, 'base64' for binary.
            metadata: Optional JSON-serialisable annotations (e.g. title).
        """
        return _artifact_dict(
            engine.save_task_artifact(
                task_id,
                _decode_content(content, encoding),
                name=name,
                media_type=media_type,
                metadata=metadata,
            )
        )

    @mcp.tool()
    def list_artifacts(
        project: str,
        feature: str | None = None,
        kind: str | None = None,
        latest_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List stored artifacts for a project.

        Args:
            project: Project slug or id.
            feature: Optional feature slug to filter by.
            kind: Optional artifact kind to filter by (e.g. 'markdown').
            latest_only: Return only the newest version of each artifact.
        """
        return [
            _artifact_dict(artifact)
            for artifact in engine.list_artifacts(
                project,
                feature_ref=feature,
                kind=ArtifactKind(kind) if kind else None,
                latest_only=latest_only,
            )
        ]

    @mcp.tool()
    def read_artifact(artifact_id: str) -> dict[str, Any]:
        """Read an artifact's metadata and content.

        Text content is returned inline (truncated at 100k characters);
        binary content is returned base64-encoded.

        Args:
            artifact_id: The artifact to read.
        """
        artifact, content = engine.read_artifact(artifact_id)
        payload = _artifact_dict(artifact)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            payload["encoding"] = "base64"
            payload["content"] = base64.b64encode(content).decode("ascii")
        else:
            payload["encoding"] = "text"
            payload["content"] = text[:_TEXT_PREVIEW_LIMIT]
            payload["truncated"] = len(text) > _TEXT_PREVIEW_LIMIT
        return payload

    # -- rendering and publishing ----------------------------------------

    @mcp.tool()
    def render_artifact(
        artifact_id: str,
        renderer: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Render a source artifact into a concrete output artifact.

        Args:
            artifact_id: The source artifact (e.g. slide-deck JSON).
            renderer: Renderer name from list_renderers; defaults to the
                standard renderer for the source's kind.
            options: Renderer-specific options (e.g. {"format": "vtt"}).
        """
        return _artifact_dict(
            engine.render_artifact(artifact_id, renderer=renderer, options=options)
        )

    @mcp.tool()
    def publish_artifact(
        artifact_id: str,
        publisher: str,
        destination: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish an artifact to a destination and record the outcome.

        Args:
            artifact_id: The artifact to deliver.
            publisher: Publisher name from list_publishers.
            destination: Publisher-specific destination (directory path,
                site root, or URL).
            options: Publisher-specific options.
        """
        return _publication_dict(
            engine.publish_artifact(artifact_id, publisher, destination, options=options)
        )

    @mcp.tool()
    def list_publications(artifact_id: str) -> list[dict[str, Any]]:
        """List the delivery history of an artifact.

        Args:
            artifact_id: The artifact whose publications to list.
        """
        return [_publication_dict(pub) for pub in engine.list_publications(artifact_id)]

    # -- capabilities -----------------------------------------------------

    @mcp.tool()
    def list_renderers() -> list[dict[str, Any]]:
        """List available renderers and what they consume/produce."""
        return [
            {
                "name": renderer.name,
                "description": renderer.description,
                "input_kinds": sorted(kind.value for kind in renderer.input_kinds),
                "output_kind": renderer.output_kind.value,
            }
            for renderer in engine.renderers.all()
        ]

    @mcp.tool()
    def list_publishers() -> list[dict[str, Any]]:
        """List available publishers."""
        return [
            {"name": publisher.name, "description": publisher.description}
            for publisher in engine.publishers.all()
        ]

    @mcp.tool()
    def list_artifact_kinds() -> list[dict[str, str]]:
        """List all artifact kinds with their expected source formats."""
        from narrate.orchestration.planner import FORMAT_HINTS

        return [
            {"kind": kind.value, "source_format": FORMAT_HINTS.get(kind, "")}
            for kind in ArtifactKind
        ]

    @mcp.tool()
    def list_tasks(project: str, status: str | None = None) -> list[dict[str, Any]]:
        """List all tasks for a project, optionally filtered by status.

        Args:
            project: Project slug or id.
            status: Optional filter: pending, in_progress, completed,
                failed, or cancelled.
        """
        return [
            _task_dict(task)
            for task in engine.list_tasks(project, status=TaskStatus(status) if status else None)
        ]

    return mcp
