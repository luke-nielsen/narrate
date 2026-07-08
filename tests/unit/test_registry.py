"""Tests for the plugin registries."""

import pytest

from narrate.exceptions import PluginNotFoundError, RenderError
from narrate.models import ArtifactKind
from narrate.rendering.base import Renderer, RenderRequest, RenderResult
from narrate.rendering.builtin.markdown import MarkdownRenderer
from narrate.rendering.registry import RendererRegistry


class FakeRenderer(Renderer):
    name = "fake"
    input_kinds = frozenset({ArtifactKind.MARKDOWN})
    output_kind = ArtifactKind.MARKDOWN
    description = "test double"

    def render(self, request: RenderRequest) -> RenderResult:
        return RenderResult(b"ok", ArtifactKind.MARKDOWN, "text/plain", ".txt")


def test_register_and_get():
    registry = RendererRegistry(discover=False)
    plugin = FakeRenderer()
    registry.register(plugin)
    assert registry.get("fake") is plugin
    assert registry.names() == ["fake"]


def test_duplicate_registration_rejected_unless_replace():
    registry = RendererRegistry(discover=False)
    registry.register(FakeRenderer())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeRenderer())
    registry.register(FakeRenderer(), replace=True)  # no error


def test_unknown_plugin_lists_available():
    registry = RendererRegistry(discover=False)
    registry.register(FakeRenderer())
    with pytest.raises(PluginNotFoundError, match="available: fake"):
        registry.get("missing")


def test_entry_point_discovery_finds_builtins():
    registry = RendererRegistry()
    assert "markdown" in registry.names()
    assert "remotion_video" in registry.names()


def test_default_for_prefers_builtin_default():
    registry = RendererRegistry()
    assert registry.default_for(ArtifactKind.SLIDE_DECK).name == "html_slides"
    assert registry.default_for(ArtifactKind.VIDEO).name == "remotion_video"


def test_default_for_falls_back_to_any_acceptor():
    registry = RendererRegistry(discover=False)
    registry.register(FakeRenderer())
    assert registry.default_for(ArtifactKind.MARKDOWN).name == "fake"


def test_default_for_without_candidates_raises():
    registry = RendererRegistry(discover=False)
    with pytest.raises(RenderError, match="no renderer registered"):
        registry.default_for(ArtifactKind.GIF)


def test_accepts_reflects_input_kinds():
    renderer = MarkdownRenderer()
    assert renderer.accepts(ArtifactKind.MARKDOWN)
    assert not renderer.accepts(ArtifactKind.VIDEO)
