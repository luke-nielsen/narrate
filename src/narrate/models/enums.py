"""Enumerations describing artifact kinds and lifecycle states."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ArtifactKind", "PublicationStatus", "TaskStatus"]


class ArtifactKind(StrEnum):
    """The kind of documentation artifact being produced.

    Kinds cover both *source* artifacts authored by AI agents (markdown,
    scripts, slide definitions, transcripts) and *derived* artifacts
    produced by renderers (videos, GIFs, presentations, subtitles,
    thumbnails).  A single kind may exist in both roles: for example a
    ``markdown`` source renders to a ``markdown`` output file.
    """

    MARKDOWN = "markdown"
    """Markdown documentation pages."""

    SCRIPT = "script"
    """Narration scripts for videos or walkthroughs."""

    TRANSCRIPT = "transcript"
    """Timestamped transcripts of narrated content."""

    SUBTITLES = "subtitles"
    """SRT/VTT subtitle files derived from transcripts."""

    SLIDE_DECK = "slide_deck"
    """HTML slide decks."""

    PRESENTATION = "presentation"
    """PowerPoint (``.pptx``) presentations."""

    VIDEO = "video"
    """Tutorial videos rendered with Remotion."""

    GIF = "gif"
    """Short animated GIF walkthroughs."""

    THUMBNAIL = "thumbnail"
    """Cover/preview images for videos and pages."""


class TaskStatus(StrEnum):
    """Lifecycle states of a documentation task.

    The happy path is ``PENDING`` -> ``IN_PROGRESS`` -> ``COMPLETED``;
    tasks may terminate early as ``FAILED`` or ``CANCELLED``.
    """

    PENDING = "pending"
    """Planned but not yet picked up by an agent."""

    IN_PROGRESS = "in_progress"
    """Claimed by an agent that is actively generating content."""

    COMPLETED = "completed"
    """Finished; at least one artifact was produced and accepted."""

    FAILED = "failed"
    """Terminated with an error recorded on the task."""

    CANCELLED = "cancelled"
    """Withdrawn before completion (e.g. the goal was removed)."""


class PublicationStatus(StrEnum):
    """Outcome of a publish operation."""

    SUCCEEDED = "succeeded"
    """The publisher confirmed delivery."""

    FAILED = "failed"
    """The publisher raised an error; details are on the record."""
