"""Shared parsing of slide-deck source documents.

Slide-deck sources are JSON documents of the shape::

    {
      "title": "Getting started with Acme",
      "subtitle": "A five minute tour",
      "slides": [
        {"title": "Sign in", "bullets": ["Open the app", "..."], "notes": "..."}
      ]
    }

Both the HTML slides renderer and the PowerPoint renderer consume this
format, so a single saved artifact can be rendered to either output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from narrate.exceptions import RenderError

__all__ = ["Deck", "Slide", "parse_deck"]


@dataclass(frozen=True, slots=True)
class Slide:
    """One slide.

    Attributes:
        title: Slide heading.
        bullets: Bullet lines, in order.
        notes: Optional speaker notes.
    """

    title: str
    bullets: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Deck:
    """A parsed slide deck.

    Attributes:
        title: Deck title (also the title slide heading).
        subtitle: Optional subtitle for the title slide.
        slides: Content slides in presentation order.
    """

    title: str
    subtitle: str = ""
    slides: tuple[Slide, ...] = field(default=())


def parse_deck(document: Any) -> Deck:  # noqa: ANN401 - JSON input
    """Parse and validate a slide-deck document.

    Args:
        document: Decoded JSON; must be an object with ``title`` and a
            non-empty ``slides`` array.

    Returns:
        The parsed deck.

    Raises:
        RenderError: If the document shape is invalid.
    """
    if not isinstance(document, dict):
        msg = "slide deck source must be a JSON object"
        raise RenderError(msg)
    title = document.get("title")
    raw_slides = document.get("slides")
    if not isinstance(title, str) or not title.strip():
        msg = 'slide deck source needs a non-empty "title"'
        raise RenderError(msg)
    if not isinstance(raw_slides, list) or not raw_slides:
        msg = 'slide deck source needs a non-empty "slides" array'
        raise RenderError(msg)

    slides: list[Slide] = []
    raw_slide_list: list[Any] = raw_slides
    for index, raw in enumerate(raw_slide_list):
        if not isinstance(raw, dict) or not isinstance(raw.get("title"), str):
            msg = f'slide {index} must be an object with a string "title"'
            raise RenderError(msg)
        bullets_raw = raw.get("bullets", [])
        if not isinstance(bullets_raw, list):
            msg = f'slide {index} "bullets" must be an array'
            raise RenderError(msg)
        bullet_list: list[Any] = bullets_raw
        slides.append(
            Slide(
                title=raw["title"],
                bullets=tuple(str(bullet) for bullet in bullet_list),
                notes=str(raw.get("notes", "")),
            )
        )
    return Deck(
        title=title,
        subtitle=str(document.get("subtitle", "")),
        slides=tuple(slides),
    )
