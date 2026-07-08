"""Integration tests driving the MCP server the way an AI assistant would."""

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

from narrate.mcp.server import create_server
from narrate.models import ArtifactKind, DocumentationTask, Project
from narrate.orchestration.engine import Orchestrator

pytestmark = pytest.mark.integration


@pytest.fixture
def server(engine: Orchestrator) -> FastMCP:
    return create_server(engine)


def call(server: Any, name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Invoke an MCP tool and return its structured result."""
    result = asyncio.run(server.call_tool(name, arguments or {}))
    if isinstance(result, tuple):  # (content blocks, structured output)
        structured = result[1]
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    parsed = [json.loads(block.text) for block in result]
    return parsed[0] if len(parsed) == 1 else parsed


def test_tool_catalog_is_complete(server: FastMCP):
    tools = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {
        "list_projects",
        "get_project",
        "get_documentation_status",
        "plan_documentation",
        "list_pending_tasks",
        "get_task",
        "claim_task",
        "save_artifact",
        "render_artifact",
        "publish_artifact",
        "complete_task",
        "fail_task",
        "list_artifacts",
        "read_artifact",
        "list_publications",
        "list_renderers",
        "list_publishers",
        "list_artifact_kinds",
        "list_tasks",
    } <= tools


def test_agent_workflow_over_mcp(
    server: FastMCP, engine: Orchestrator, project: Project, tmp_path: Path
):
    # Discover.
    projects = call(server, "list_projects")
    assert projects[0]["slug"] == "acme-notes"
    detail = call(server, "get_project", {"project": "acme-notes"})
    assert len(detail["features"]) == 2
    assert len(detail["goals"]) == 2

    # Plan and pick up work.
    planned = call(server, "plan_documentation", {"project": "acme-notes"})
    assert len(planned) == 4
    pending = call(server, "list_pending_tasks", {"project": "acme-notes"})
    task = next(t for t in pending if t["kind"] == "markdown")
    claimed = call(server, "claim_task", {"task_id": task["id"], "agent_name": "claude"})
    assert claimed["status"] == "in_progress"
    assert claimed["claimed_by"] == "claude"

    # Generate, render, publish, complete.
    artifact = call(
        server,
        "save_artifact",
        {
            "task_id": task["id"],
            "content": "# Shared notebooks\n\nHow to collaborate.",
            "metadata": {"title": "Shared notebooks"},
        },
    )
    rendered = call(server, "render_artifact", {"artifact_id": artifact["id"]})
    assert rendered["derived_from"] == artifact["id"]
    publication = call(
        server,
        "publish_artifact",
        {
            "artifact_id": rendered["id"],
            "publisher": "filesystem",
            "destination": str(tmp_path / "out"),
        },
    )
    assert publication["status"] == "succeeded"
    done = call(server, "complete_task", {"task_id": task["id"]})
    assert done["status"] == "completed"

    # Status reflects the work.
    status = call(server, "get_documentation_status", {"project": "acme-notes"})
    assert status["tasks_by_status"]["completed"] == 1
    assert status["artifacts"] == 2


def test_save_artifact_base64_roundtrip(server: FastMCP, engine: Orchestrator, project: Project):
    planned = call(server, "plan_documentation", {"project": "acme-notes"})
    task = planned[0]
    call(server, "claim_task", {"task_id": task["id"]})
    payload = bytes(range(256))
    artifact = call(
        server,
        "save_artifact",
        {
            "task_id": task["id"],
            "content": base64.b64encode(payload).decode(),
            "encoding": "base64",
            "name": "binary.bin",
        },
    )
    read = call(server, "read_artifact", {"artifact_id": artifact["id"]})
    assert read["encoding"] == "base64"
    assert base64.b64decode(read["content"]) == payload


def test_read_artifact_returns_text_inline(
    server: FastMCP, engine: Orchestrator, claimed_task: DocumentationTask
):
    saved = engine.save_task_artifact(claimed_task.id, b"# Hello")
    read = call(server, "read_artifact", {"artifact_id": saved.id})
    assert read["encoding"] == "text"
    assert read["content"] == "# Hello"
    assert read["truncated"] is False


def test_capability_listing(server: FastMCP):
    renderers = call(server, "list_renderers")
    assert any(r["name"] == "remotion_video" for r in renderers)
    publishers = call(server, "list_publishers")
    assert any(p["name"] == "static_site" for p in publishers)
    kinds = call(server, "list_artifact_kinds")
    assert {k["kind"] for k in kinds} == {kind.value for kind in ArtifactKind}


def test_errors_surface_as_tool_errors(server: FastMCP):
    with pytest.raises(Exception, match="not found"):
        call(server, "get_task", {"task_id": "missing"})
