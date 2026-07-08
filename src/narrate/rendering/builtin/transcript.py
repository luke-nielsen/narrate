"""Human-readable transcript renderer."""

from __future__ import annotations

from typing import ClassVar

from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult
from narrate.rendering.builtin.cues import format_timestamp, parse_cues

__all__ = ["TranscriptRenderer"]


class TranscriptRenderer(Renderer):
    """Render timed cues into a readable plain-text transcript."""

    name: ClassVar[str] = "transcript"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset({ArtifactKind.TRANSCRIPT})
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.TRANSCRIPT
    description: ClassVar[str] = "Format timed cues as a readable transcript"

    def render(self, request: RenderRequest) -> RenderResult:
        """Produce the transcript text.

        Raises:
            RenderError: If the cue document is malformed.
        """
        self.check_input(request)
        cues = parse_cues(request.json())
        lines: list[str] = []
        for cue in cues:
            stamp = format_timestamp(cue.start, separator=".")
            prefix = f"{cue.speaker}: " if cue.speaker else ""
            lines.append(f"[{stamp}] {prefix}{cue.text}")
        rendered = "\n".join(lines) + "\n"
        return RenderResult(
            content=rendered.encode("utf-8"),
            kind=self.output_kind,
            media_type="text/plain",
            suffix=".txt",
            metadata={"cues": len(cues), "duration_seconds": cues[-1].end},
        )
