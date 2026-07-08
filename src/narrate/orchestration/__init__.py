"""Orchestration layer: the documentation lifecycle engine.

The :class:`~narrate.orchestration.engine.Orchestrator` is the single
entry point for every interface (CLI, MCP server, embedding applications).
It owns transaction boundaries, coordinates the planner, blob store,
renderer and publisher registries, and enforces task lifecycle rules.
"""

from narrate.orchestration.engine import Orchestrator
from narrate.orchestration.planner import TaskPlanner

__all__ = ["Orchestrator", "TaskPlanner"]
