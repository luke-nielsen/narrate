"""Self-contained HTML slide deck renderer."""

from __future__ import annotations

import html
from typing import ClassVar

from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult
from narrate.rendering.builtin.decks import Deck, parse_deck

__all__ = ["HtmlSlidesRenderer"]

_STYLE = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
       background: #111827; color: #f9fafb; }
.slide { display: none; width: 100vw; height: 100vh; padding: 8vh 10vw;
         flex-direction: column; justify-content: center; }
.slide.active { display: flex; }
.slide h1 { font-size: 3.2rem; margin-bottom: 1rem; }
.slide h2 { font-size: 2.4rem; margin-bottom: 1.5rem; }
.slide p.subtitle { font-size: 1.4rem; color: #9ca3af; }
.slide ul { font-size: 1.5rem; line-height: 2.2rem; margin-left: 1.5rem; }
.counter { position: fixed; bottom: 1rem; right: 1.5rem; color: #6b7280;
           font-size: 0.9rem; }
"""

_SCRIPT = """
const slides = document.querySelectorAll('.slide');
const counter = document.querySelector('.counter');
let index = 0;
function show(next) {
  index = Math.min(Math.max(next, 0), slides.length - 1);
  slides.forEach((slide, i) => slide.classList.toggle('active', i === index));
  counter.textContent = `${index + 1} / ${slides.length}`;
}
document.addEventListener('keydown', (event) => {
  if (['ArrowRight', ' ', 'PageDown'].includes(event.key)) show(index + 1);
  if (['ArrowLeft', 'PageUp'].includes(event.key)) show(index - 1);
});
document.addEventListener('click', () => show(index + 1));
show(0);
"""


class HtmlSlidesRenderer(Renderer):
    """Render slide-deck sources into a single-file HTML presentation.

    The output has zero external dependencies (inline CSS and JS) and is
    navigated with arrow keys, space, or clicks -- suitable for direct
    publishing to any static host.
    """

    name: ClassVar[str] = "html_slides"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset({ArtifactKind.SLIDE_DECK})
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.SLIDE_DECK
    description: ClassVar[str] = "Render slide decks as self-contained HTML presentations"

    def render(self, request: RenderRequest) -> RenderResult:
        """Produce the HTML deck.

        Raises:
            RenderError: If the deck document is malformed.
        """
        self.check_input(request)
        deck = parse_deck(request.json())
        rendered = self._document(deck)
        return RenderResult(
            content=rendered.encode("utf-8"),
            kind=self.output_kind,
            media_type="text/html",
            suffix=".html",
            metadata={"slides": len(deck.slides) + 1, "title": deck.title},
        )

    @staticmethod
    def _document(deck: Deck) -> str:
        sections: list[str] = [
            "<section class='slide active'>"
            f"<h1>{html.escape(deck.title)}</h1>"
            f"<p class='subtitle'>{html.escape(deck.subtitle)}</p>"
            "</section>"
        ]
        for slide in deck.slides:
            bullets = "".join(f"<li>{html.escape(bullet)}</li>" for bullet in slide.bullets)
            notes = f"<!-- notes: {html.escape(slide.notes)} -->" if slide.notes else ""
            sections.append(
                f"<section class='slide'><h2>{html.escape(slide.title)}</h2>"
                f"<ul>{bullets}</ul>{notes}</section>"
            )
        body = "\n".join(sections)
        return (
            "<!DOCTYPE html>\n"
            f"<html lang='en'><head><meta charset='utf-8'>"
            f"<title>{html.escape(deck.title)}</title>"
            f"<style>{_STYLE}</style></head>\n"
            f"<body>\n{body}\n<div class='counter'></div>"
            f"<script>{_SCRIPT}</script></body></html>\n"
        )
