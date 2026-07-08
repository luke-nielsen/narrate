"""Thumbnail/cover image renderer (requires the ``media`` extra).

Thumbnail sources are JSON documents::

    {
      "title": "Getting started",
      "subtitle": "Acme in 5 minutes",
      "width": 1280,
      "height": 720,
      "background": "#111827",
      "accent": "#6366f1"
    }
"""

from __future__ import annotations

import io
from typing import ClassVar

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult

__all__ = ["ThumbnailRenderer"]


class ThumbnailRenderer(Renderer):
    """Render title cards as PNG thumbnails.

    Uses Pillow; install with ``pip install narrate[media]``.
    """

    name: ClassVar[str] = "thumbnail"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset({ArtifactKind.THUMBNAIL})
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.THUMBNAIL
    description: ClassVar[str] = "Render title cards as PNG thumbnails"

    def render(self, request: RenderRequest) -> RenderResult:
        """Produce the PNG thumbnail.

        Raises:
            RenderError: If Pillow is missing or the spec is malformed.
        """
        self.check_input(request)
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            msg = "Pillow is required for the thumbnail renderer: pip install 'narrate[media]'"
            raise RenderError(msg) from exc

        spec = request.json()
        if not isinstance(spec, dict) or not str(spec.get("title", "")).strip():
            msg = 'thumbnail source must be a JSON object with a "title"'
            raise RenderError(msg)

        width = int(spec.get("width", 1280))
        height = int(spec.get("height", 720))
        background = str(spec.get("background", "#111827"))
        accent = str(spec.get("accent", "#6366f1"))
        title = str(spec["title"])
        subtitle = str(spec.get("subtitle", ""))

        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, height - height // 24, width, height), fill=accent)

        margin = width // 12
        draw.text((margin, height // 3), title, fill="#f9fafb")
        if subtitle:
            draw.text((margin, height // 3 + height // 10), subtitle, fill="#9ca3af")

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return RenderResult(
            content=buffer.getvalue(),
            kind=self.output_kind,
            media_type="image/png",
            suffix=".png",
            metadata={"width": width, "height": height, "title": title},
        )
