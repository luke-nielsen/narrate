"""Renderer plugin contract."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from narrate.exceptions import RenderError
from narrate.models import ArtifactKind

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from narrate.models import Artifact

__all__ = ["RenderRequest", "RenderResult", "Renderer"]


@dataclass(frozen=True, slots=True)
class RenderRequest:
    """Everything a renderer needs to do its job.

    Attributes:
        artifact: Metadata of the source artifact being rendered.
        content: Raw bytes of the source artifact.
        workspace: A scratch directory the renderer may write
            intermediate files to (e.g. a Remotion project bundle).
        options: Renderer-specific options supplied by the caller.
    """

    artifact: Artifact
    content: bytes
    workspace: Path
    options: Mapping[str, Any] = field(default_factory=dict)

    def text(self, encoding: str = "utf-8") -> str:
        """Decode the source content as text.

        Raises:
            RenderError: If the content is not valid text.
        """
        try:
            return self.content.decode(encoding)
        except UnicodeDecodeError as exc:
            msg = f"source artifact {self.artifact.id} is not valid {encoding} text"
            raise RenderError(msg) from exc

    def json(self) -> Any:  # noqa: ANN401 - JSON is inherently dynamic
        """Parse the source content as JSON.

        Raises:
            RenderError: If the content is not valid JSON.
        """
        try:
            return json.loads(self.text())
        except json.JSONDecodeError as exc:
            msg = f"source artifact {self.artifact.id} is not valid JSON: {exc}"
            raise RenderError(msg) from exc


@dataclass(frozen=True, slots=True)
class RenderResult:
    """The output of a successful render.

    Attributes:
        content: Rendered bytes, stored verbatim as a derived artifact.
        kind: Artifact kind of the output.
        media_type: IANA media type of ``content``.
        suffix: Filename suffix for the output, including the dot.
        metadata: Renderer-provided annotations persisted with the
            derived artifact (e.g. slide count, duration, mode).
    """

    content: bytes
    kind: ArtifactKind
    media_type: str
    suffix: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Renderer(ABC):
    """Base class for renderer plugins.

    Subclasses declare what they consume and produce via class attributes
    and implement :meth:`render`.  Renderers must be stateless and
    side-effect free outside ``request.workspace``: the engine owns
    persistence of results.

    Attributes:
        name: Unique registry key, also used in CLI/MCP calls.
        input_kinds: Source artifact kinds this renderer accepts.
        output_kind: Artifact kind of the produced output.
        description: One-line summary shown in plugin listings.
    """

    name: ClassVar[str]
    input_kinds: ClassVar[frozenset[ArtifactKind]]
    output_kind: ClassVar[ArtifactKind]
    description: ClassVar[str] = ""

    def accepts(self, kind: ArtifactKind) -> bool:
        """Return whether this renderer can consume ``kind`` sources."""
        return kind in self.input_kinds

    def check_input(self, request: RenderRequest) -> None:
        """Validate that the request's source kind is acceptable.

        Raises:
            RenderError: If the source artifact kind is unsupported.
        """
        if not self.accepts(request.artifact.kind):
            supported = ", ".join(sorted(k.value for k in self.input_kinds))
            msg = (
                f"renderer {self.name!r} cannot render {request.artifact.kind.value!r} "
                f"sources (supported: {supported})"
            )
            raise RenderError(msg)

    @abstractmethod
    def render(self, request: RenderRequest) -> RenderResult:
        """Produce output bytes from a source artifact.

        Args:
            request: Source artifact content, metadata, and options.

        Returns:
            The rendered output.

        Raises:
            RenderError: If the source is invalid or rendering fails.
        """
