"""Narrate: AI-native documentation orchestration platform.

Narrate orchestrates the complete documentation lifecycle for software
products.  Humans (or agents) describe *what* should be documented --
projects, features, and documentation goals -- and AI assistants connected
over the Model Context Protocol (MCP) perform the work one deterministic
tool call at a time: discover pending tasks, save generated artifacts,
render them into concrete outputs, and publish them to destinations.

The package is organised into strict layers:

- :mod:`narrate.models` -- immutable Pydantic domain models.
- :mod:`narrate.storage` -- SQLAlchemy persistence and the blob store.
- :mod:`narrate.rendering` / :mod:`narrate.publishing` -- plugin registries.
- :mod:`narrate.orchestration` -- the lifecycle engine tying it together.
- :mod:`narrate.mcp` -- the MCP server exposed to AI assistants.
- :mod:`narrate.cli` -- the Typer command line interface.
"""

from narrate.config import NarrateSettings
from narrate.container import Container
from narrate.orchestration.engine import Orchestrator

__version__ = "0.1.0"

__all__ = [
    "Container",
    "NarrateSettings",
    "Orchestrator",
    "__version__",
]
