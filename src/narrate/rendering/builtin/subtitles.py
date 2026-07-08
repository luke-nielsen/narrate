"""Subtitle renderer producing SRT or WebVTT files."""

from __future__ import annotations

from typing import ClassVar

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult
from narrate.rendering.builtin.cues import Cue, format_timestamp, parse_cues

__all__ = ["SubtitleRenderer"]


class SubtitleRenderer(Renderer):
    """Render timed cues into subtitle files.

    Accepts transcript-style cue documents and emits SRT (default) or
    WebVTT depending on ``options["format"]`` (``"srt"`` or ``"vtt"``).
    """

    name: ClassVar[str] = "subtitles"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset(
        {ArtifactKind.TRANSCRIPT, ArtifactKind.SUBTITLES}
    )
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.SUBTITLES
    description: ClassVar[str] = "Convert timed cues to SRT or WebVTT subtitles"

    def render(self, request: RenderRequest) -> RenderResult:
        """Produce the subtitle file.

        Raises:
            RenderError: If the cue document is malformed or the format
                option is not ``"srt"`` or ``"vtt"``.
        """
        self.check_input(request)
        cues = parse_cues(request.json())
        subtitle_format = str(request.options.get("format", "srt")).lower()
        if subtitle_format == "srt":
            rendered, media_type, suffix = self._srt(cues), "application/x-subrip", ".srt"
        elif subtitle_format == "vtt":
            rendered, media_type, suffix = self._vtt(cues), "text/vtt", ".vtt"
        else:
            msg = f"unsupported subtitle format {subtitle_format!r} (use 'srt' or 'vtt')"
            raise RenderError(msg)
        return RenderResult(
            content=rendered.encode("utf-8"),
            kind=self.output_kind,
            media_type=media_type,
            suffix=suffix,
            metadata={"cues": len(cues), "format": subtitle_format},
        )

    @staticmethod
    def _srt(cues: list[Cue]) -> str:
        blocks = [
            f"{index}\n{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n{cue.text}"
            for index, cue in enumerate(cues, start=1)
        ]
        return "\n\n".join(blocks) + "\n"

    @staticmethod
    def _vtt(cues: list[Cue]) -> str:
        blocks = [
            f"{format_timestamp(cue.start, separator='.')} --> "
            f"{format_timestamp(cue.end, separator='.')}\n{cue.text}"
            for cue in cues
        ]
        return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"
