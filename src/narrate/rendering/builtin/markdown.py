"""Markdown documentation renderer."""

from __future__ import annotations

from typing import ClassVar

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult

__all__ = ["MarkdownRenderer"]


class MarkdownRenderer(Renderer):
    """Render markdown sources into publishable ``.md`` files.

    The renderer normalises whitespace, guarantees a top-level heading,
    and (unless ``options["front_matter"]`` is false) prepends YAML front
    matter carrying artifact provenance so downstream static-site
    generators can index the page.
    """

    name: ClassVar[str] = "markdown"
    input_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset({ArtifactKind.MARKDOWN})
    output_kind: ClassVar[ArtifactKind] = ArtifactKind.MARKDOWN
    description: ClassVar[str] = "Normalise markdown and add provenance front matter"

    def render(self, request: RenderRequest) -> RenderResult:
        """Produce the final markdown document.

        Raises:
            RenderError: If the source is empty or not text.
        """
        self.check_input(request)
        body = request.text().strip()
        if not body:
            msg = f"markdown source {request.artifact.id} is empty"
            raise RenderError(msg)

        title = str(request.options.get("title") or request.artifact.metadata.get("title") or "")
        if not body.startswith("#"):
            heading = title or request.artifact.name.rsplit(".", 1)[0].replace("-", " ").title()
            body = f"# {heading}\n\n{body}"

        rendered = body + "\n"
        if request.options.get("front_matter", True):
            front_matter = "\n".join(
                [
                    "---",
                    f"artifact_id: {request.artifact.id}",
                    f"artifact_version: {request.artifact.version}",
                    f"project_id: {request.artifact.project_id}",
                    f"generated_by: {request.artifact.created_by}",
                    "---",
                    "",
                ]
            )
            rendered = front_matter + rendered

        line_count = rendered.count("\n")
        return RenderResult(
            content=rendered.encode("utf-8"),
            kind=self.output_kind,
            media_type="text/markdown",
            suffix=".md",
            metadata={"lines": line_count},
        )
