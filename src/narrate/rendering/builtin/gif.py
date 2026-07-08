"""Animated GIF renderer (requires the ``media`` extra).

GIF sources are JSON documents describing text frames::

    {
      "width": 640,
      "height": 360,
      "frames": [
        {"text": "Step 1: open settings", "duration_ms": 1500,
         "background": "#111827", "color": "#f9fafb"}
      ]
    }
"""

from __future__ import annotations

from typing import Any, ClassVar

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult

__all__ = ["GifRenderer"]


class GifRenderer(Renderer):
    """Render frame specs into animated GIF walkthroughs.

    Uses Pillow; install with ``pip install narrate[media]``.
    """

    name: ClassVar[str] = "gif"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset({ArtifactKind.GIF})
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.GIF
    description: ClassVar[str] = "Render text frame specs as animated GIFs"

    def render(self, request: RenderRequest) -> RenderResult:
        """Produce the animated GIF.

        Raises:
            RenderError: If Pillow is missing or the spec is malformed.
        """
        self.check_input(request)
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            msg = "Pillow is required for the gif renderer: pip install 'narrate[media]'"
            raise RenderError(msg) from exc

        spec = request.json()
        if not isinstance(spec, dict) or not isinstance(spec.get("frames"), list):
            msg = 'gif source must be a JSON object with a "frames" array'
            raise RenderError(msg)
        frames_spec: list[Any] = spec["frames"]
        if not frames_spec:
            msg = "gif source contains no frames"
            raise RenderError(msg)

        width = int(spec.get("width", 640))
        height = int(spec.get("height", 360))
        images: list[Any] = []
        durations: list[int] = []
        for index, frame in enumerate(frames_spec):
            if not isinstance(frame, dict) or "text" not in frame:
                msg = f'frame {index} must be an object with "text"'
                raise RenderError(msg)
            background = str(frame.get("background", "#111827"))
            color = str(frame.get("color", "#f9fafb"))
            image = Image.new("RGB", (width, height), background)
            draw = ImageDraw.Draw(image)
            self._draw_centered_text(draw, str(frame["text"]), width, height, color)
            images.append(image)
            durations.append(int(frame.get("duration_ms", 1500)))

        import io

        buffer = io.BytesIO()
        images[0].save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
        )
        return RenderResult(
            content=buffer.getvalue(),
            kind=self.output_kind,
            media_type="image/gif",
            suffix=".gif",
            metadata={
                "frames": len(images),
                "width": width,
                "height": height,
                "duration_ms": sum(durations),
            },
        )

    @staticmethod
    def _draw_centered_text(
        draw: Any,  # noqa: ANN401 - PIL types unavailable without the extra
        text: str,
        width: int,
        height: int,
        color: str,
    ) -> None:
        """Draw ``text`` centred, wrapping long lines to fit the frame."""
        import textwrap

        wrapped = textwrap.fill(text, width=max(10, width // 12))
        bbox = draw.multiline_textbbox((0, 0), wrapped, align="center")
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        position = ((width - text_width) / 2, (height - text_height) / 2)
        draw.multiline_text(position, wrapped, fill=color, align="center")
