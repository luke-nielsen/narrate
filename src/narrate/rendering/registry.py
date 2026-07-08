"""Registry of renderer plugins."""

from __future__ import annotations

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind
from narrate.plugins import PluginRegistry
from narrate.rendering.base import Renderer

__all__ = ["RendererRegistry"]

ENTRY_POINT_GROUP = "narrate.renderers"

_DEFAULTS: dict[ArtifactKind, str] = {
    ArtifactKind.MARKDOWN: "markdown",
    ArtifactKind.SCRIPT: "script",
    ArtifactKind.TRANSCRIPT: "transcript",
    ArtifactKind.SUBTITLES: "subtitles",
    ArtifactKind.SLIDE_DECK: "html_slides",
    ArtifactKind.PRESENTATION: "pptx",
    ArtifactKind.VIDEO: "remotion_video",
    ArtifactKind.GIF: "gif",
    ArtifactKind.THUMBNAIL: "thumbnail",
}


class RendererRegistry(PluginRegistry[Renderer]):
    """Renderer registry with per-kind default selection.

    Multiple renderers may accept the same source kind (e.g. a slide deck
    renders to HTML *or* PowerPoint), so callers can either name a
    renderer explicitly or rely on :meth:`default_for` to pick the
    built-in default for the source kind.
    """

    def __init__(self, *, discover: bool = True) -> None:
        """Initialise the registry.

        Args:
            discover: Load plugins from entry points (disable in tests to
                start from an empty registry).
        """
        super().__init__("renderer", ENTRY_POINT_GROUP if discover else None)

    def default_for(self, kind: ArtifactKind) -> Renderer:
        """Return the default renderer for a source artifact kind.

        Falls back to the only registered renderer accepting ``kind`` if
        the built-in default is absent.

        Raises:
            RenderError: If no registered renderer accepts ``kind``.
        """
        default_name = _DEFAULTS.get(kind)
        if default_name is not None and default_name in self.names():
            return self.get(default_name)
        candidates = [renderer for renderer in self.all() if renderer.accepts(kind)]
        if not candidates:
            msg = f"no renderer registered for source kind {kind.value!r}"
            raise RenderError(msg)
        return candidates[0]
