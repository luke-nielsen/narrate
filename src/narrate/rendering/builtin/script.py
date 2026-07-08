"""Narration script renderer."""

from __future__ import annotations

import textwrap
from typing import ClassVar

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult

__all__ = ["ScriptRenderer"]


class ScriptRenderer(Renderer):
    """Render narration scripts into teleprompter-friendly text files.

    The source is plain text; paragraphs are re-wrapped to a configurable
    column width (``options["width"]``, default 72) and numbered so a
    narrator or TTS pipeline can reference sections deterministically.
    """

    name: ClassVar[str] = "script"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset({ArtifactKind.SCRIPT})
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.SCRIPT
    description: ClassVar[str] = "Format narration scripts for narrators and TTS pipelines"

    def render(self, request: RenderRequest) -> RenderResult:
        """Produce the formatted script.

        Raises:
            RenderError: If the source is empty or not text.
        """
        self.check_input(request)
        raw = request.text().strip()
        if not raw:
            msg = f"script source {request.artifact.id} is empty"
            raise RenderError(msg)
        width = int(request.options.get("width", 72))

        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        sections: list[str] = []
        for number, paragraph in enumerate(paragraphs, start=1):
            wrapped = textwrap.fill(" ".join(paragraph.split()), width=width)
            sections.append(f"[{number:02d}]\n{wrapped}")

        title = request.artifact.metadata.get("title", request.artifact.name)
        header = f"NARRATION SCRIPT: {title}\n{'=' * min(width, 72)}\n"
        rendered = header + "\n\n".join(sections) + "\n"
        word_count = len(raw.split())
        return RenderResult(
            content=rendered.encode("utf-8"),
            kind=self.output_kind,
            media_type="text/plain",
            suffix=".txt",
            metadata={"sections": len(sections), "words": word_count},
        )
