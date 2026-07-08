"""Rendering layer: turn stored source artifacts into concrete outputs.

A *renderer* is a plugin that accepts one source artifact (markdown text,
slide definitions, transcript cues, a video composition spec, ...) and
returns rendered bytes plus metadata.  The orchestration engine stores the
result as a new, derived artifact -- renderers never touch storage.
"""

from narrate.rendering.base import Renderer, RenderRequest, RenderResult
from narrate.rendering.registry import RendererRegistry

__all__ = ["RenderRequest", "RenderResult", "Renderer", "RendererRegistry"]
