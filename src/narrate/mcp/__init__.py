"""MCP layer: expose the orchestration engine to AI assistants.

The server is a thin adapter -- every tool delegates straight to
:class:`~narrate.orchestration.engine.Orchestrator` and serialises domain
models to JSON-friendly dictionaries.  No business logic lives here.
"""

from narrate.mcp.server import create_server

__all__ = ["create_server"]
