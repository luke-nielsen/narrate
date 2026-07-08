"""Command line interface for operating Narrate.

The CLI is for humans setting up projects and inspecting progress; AI
agents interact through the MCP server (``narrate serve``) instead.
"""

from narrate.cli.main import app

__all__ = ["app"]
