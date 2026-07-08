"""Shared parsing of timed transcript cues.

Transcript-family source artifacts are JSON documents of the shape::

    {"cues": [{"start": 0.0, "end": 3.2, "text": "Welcome to Acme."}, ...]}

Both the transcript and subtitle renderers consume this format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from narrate.exceptions import RenderError

__all__ = ["Cue", "format_timestamp", "parse_cues"]


@dataclass(frozen=True, slots=True)
class Cue:
    """One timed caption.

    Attributes:
        start: Start time in seconds.
        end: End time in seconds.
        text: Caption text (may contain newlines).
        speaker: Optional speaker label.
    """

    start: float
    end: float
    text: str
    speaker: str | None = None


def parse_cues(document: Any) -> list[Cue]:  # noqa: ANN401 - JSON input
    """Parse and validate a cue document.

    Args:
        document: Decoded JSON; must be ``{"cues": [...]}``.

    Returns:
        Cues in input order.

    Raises:
        RenderError: If the document shape or any cue timing is invalid.
    """
    if not isinstance(document, dict) or not isinstance(document.get("cues"), list):
        msg = 'transcript source must be a JSON object with a "cues" array'
        raise RenderError(msg)
    cues: list[Cue] = []
    raw_cues: list[Any] = document["cues"]
    for index, raw in enumerate(raw_cues):
        if not isinstance(raw, dict):
            msg = f"cue {index} must be an object"
            raise RenderError(msg)
        try:
            start = float(raw["start"])
            end = float(raw["end"])
            text = str(raw["text"])
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"cue {index} needs numeric 'start'/'end' and 'text': {exc}"
            raise RenderError(msg) from exc
        if start < 0 or end < start:
            msg = f"cue {index} has invalid timing: start={start}, end={end}"
            raise RenderError(msg)
        speaker_raw = raw.get("speaker")
        speaker = str(speaker_raw) if speaker_raw is not None else None
        cues.append(Cue(start=start, end=end, text=text, speaker=speaker))
    if not cues:
        msg = "transcript source contains no cues"
        raise RenderError(msg)
    return cues


def format_timestamp(seconds: float, *, separator: str = ",") -> str:
    """Format seconds as ``HH:MM:SS<sep>mmm`` (SRT uses ``,``, VTT ``.``)."""
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"
