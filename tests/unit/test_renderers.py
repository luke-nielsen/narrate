"""Tests for every built-in renderer."""

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from narrate.exceptions import RenderError
from narrate.models import Artifact, ArtifactKind
from narrate.rendering.base import RenderRequest
from narrate.rendering.builtin.gif import GifRenderer
from narrate.rendering.builtin.html_slides import HtmlSlidesRenderer
from narrate.rendering.builtin.markdown import MarkdownRenderer
from narrate.rendering.builtin.pptx import PptxRenderer
from narrate.rendering.builtin.remotion import RemotionRenderer
from narrate.rendering.builtin.script import ScriptRenderer
from narrate.rendering.builtin.subtitles import SubtitleRenderer
from narrate.rendering.builtin.thumbnail import ThumbnailRenderer
from narrate.rendering.builtin.transcript import TranscriptRenderer

CUES = {
    "cues": [
        {"start": 0, "end": 2.5, "text": "Welcome to Acme.", "speaker": "Host"},
        {"start": 2.5, "end": 6, "text": "Let's create a notebook."},
    ]
}

DECK = {
    "title": "Acme in five minutes",
    "subtitle": "A quick tour",
    "slides": [
        {"title": "Notebooks", "bullets": ["Create", "Share <safely>"], "notes": "smile"},
        {"title": "Search", "bullets": ["Instant results"]},
    ],
}


def request_for(
    kind: ArtifactKind,
    content: bytes,
    tmp_path: Path,
    options: dict[str, Any] | None = None,
) -> RenderRequest:
    artifact = Artifact(
        project_id="p1",
        kind=kind,
        name=f"source.{kind.value}",
        content_hash="0" * 64,
        size_bytes=len(content),
        metadata={"title": "Test Title"},
    )
    return RenderRequest(
        artifact=artifact, content=content, workspace=tmp_path, options=options or {}
    )


def test_markdown_adds_heading_and_front_matter(tmp_path: Path):
    request = request_for(ArtifactKind.MARKDOWN, b"Just a paragraph.", tmp_path)
    result = MarkdownRenderer().render(request)
    text = result.content.decode()
    assert text.startswith("---\n")
    assert "artifact_id:" in text
    assert "# Test Title" in text
    assert result.media_type == "text/markdown"
    assert result.suffix == ".md"


def test_markdown_front_matter_can_be_disabled(tmp_path: Path):
    request = request_for(
        ArtifactKind.MARKDOWN, b"# Ready\n\nBody.", tmp_path, {"front_matter": False}
    )
    text = MarkdownRenderer().render(request).content.decode()
    assert text.startswith("# Ready")


def test_markdown_rejects_empty_source(tmp_path: Path):
    with pytest.raises(RenderError, match="empty"):
        MarkdownRenderer().render(request_for(ArtifactKind.MARKDOWN, b"   ", tmp_path))


def test_markdown_rejects_wrong_kind(tmp_path: Path):
    with pytest.raises(RenderError, match="cannot render"):
        MarkdownRenderer().render(request_for(ArtifactKind.VIDEO, b"x", tmp_path))


def test_script_numbers_paragraphs(tmp_path: Path):
    source = b"First scene narration.\n\nSecond scene narration."
    result = ScriptRenderer().render(request_for(ArtifactKind.SCRIPT, source, tmp_path))
    text = result.content.decode()
    assert "[01]" in text and "[02]" in text
    assert result.metadata["sections"] == 2


def test_transcript_formats_cues_with_speakers(tmp_path: Path):
    source = json.dumps(CUES).encode()
    result = TranscriptRenderer().render(request_for(ArtifactKind.TRANSCRIPT, source, tmp_path))
    text = result.content.decode()
    assert "[00:00:00.000] Host: Welcome to Acme." in text
    assert result.metadata["duration_seconds"] == 6


def test_transcript_rejects_bad_timing(tmp_path: Path):
    bad = json.dumps({"cues": [{"start": 5, "end": 1, "text": "x"}]}).encode()
    with pytest.raises(RenderError, match="invalid timing"):
        TranscriptRenderer().render(request_for(ArtifactKind.TRANSCRIPT, bad, tmp_path))


def test_subtitles_srt_format(tmp_path: Path):
    source = json.dumps(CUES).encode()
    result = SubtitleRenderer().render(request_for(ArtifactKind.TRANSCRIPT, source, tmp_path))
    text = result.content.decode()
    assert text.startswith("1\n00:00:00,000 --> 00:00:02,500\nWelcome to Acme.")
    assert result.suffix == ".srt"


def test_subtitles_vtt_format(tmp_path: Path):
    source = json.dumps(CUES).encode()
    result = SubtitleRenderer().render(
        request_for(ArtifactKind.TRANSCRIPT, source, tmp_path, {"format": "vtt"})
    )
    text = result.content.decode()
    assert text.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:02.500" in text


def test_subtitles_unknown_format_rejected(tmp_path: Path):
    source = json.dumps(CUES).encode()
    with pytest.raises(RenderError, match="unsupported subtitle format"):
        SubtitleRenderer().render(
            request_for(ArtifactKind.TRANSCRIPT, source, tmp_path, {"format": "ass"})
        )


def test_html_slides_escapes_and_counts(tmp_path: Path):
    source = json.dumps(DECK).encode()
    result = HtmlSlidesRenderer().render(request_for(ArtifactKind.SLIDE_DECK, source, tmp_path))
    html_text = result.content.decode()
    assert "Share &lt;safely&gt;" in html_text  # escaped
    assert html_text.count("<section class='slide") == 3  # title + 2 content
    assert result.metadata["slides"] == 3
    assert result.media_type == "text/html"


def test_html_slides_rejects_missing_title(tmp_path: Path):
    bad = json.dumps({"slides": [{"title": "x"}]}).encode()
    with pytest.raises(RenderError, match='"title"'):
        HtmlSlidesRenderer().render(request_for(ArtifactKind.SLIDE_DECK, bad, tmp_path))


def test_pptx_builds_presentation(tmp_path: Path):
    pytest.importorskip("pptx")
    source = json.dumps(DECK).encode()
    result = PptxRenderer().render(request_for(ArtifactKind.SLIDE_DECK, source, tmp_path))
    assert result.suffix == ".pptx"
    from pptx import Presentation

    deck = Presentation(io.BytesIO(result.content))
    assert len(deck.slides) == 3


def test_remotion_bundle_is_complete_and_deterministic(tmp_path: Path):
    spec = {
        "title": "Tour",
        "scenes": [
            {"heading": "Sign in", "body": "Open the app.", "duration_seconds": 3},
            {"heading": "Create", "body": "Make a note.", "duration_seconds": 5},
        ],
    }
    source = json.dumps(spec).encode()
    renderer = RemotionRenderer()
    first = renderer.render(request_for(ArtifactKind.VIDEO, source, tmp_path))
    second = renderer.render(request_for(ArtifactKind.VIDEO, source, tmp_path))
    assert first.content == second.content  # deterministic zip
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        names = set(archive.namelist())
        assert {"package.json", "props.json", "src/Root.tsx", "src/NarrateVideo.tsx"} <= names
        props = json.loads(archive.read("props.json"))
    assert props["fps"] == 30  # defaults applied
    assert first.metadata["duration_seconds"] == 8
    assert first.metadata["mode"] == "bundle"


def test_remotion_rejects_sceneless_spec(tmp_path: Path):
    with pytest.raises(RenderError, match="scenes"):
        RemotionRenderer().render(request_for(ArtifactKind.VIDEO, b'{"scenes": []}', tmp_path))


def test_remotion_unknown_mode_rejected(tmp_path: Path):
    source = json.dumps({"scenes": [{"heading": "x"}]}).encode()
    with pytest.raises(RenderError, match="unknown remotion mode"):
        RemotionRenderer().render(
            request_for(ArtifactKind.VIDEO, source, tmp_path, {"mode": "hologram"})
        )


def test_gif_renders_animated_frames(tmp_path: Path):
    pytest.importorskip("PIL")
    spec = {
        "width": 120,
        "height": 80,
        "frames": [
            {"text": "Step 1", "duration_ms": 500},
            {"text": "Step 2", "duration_ms": 700},
        ],
    }
    result = GifRenderer().render(
        request_for(ArtifactKind.GIF, json.dumps(spec).encode(), tmp_path)
    )
    from PIL import Image

    image = Image.open(io.BytesIO(result.content))
    assert image.format == "GIF"
    assert getattr(image, "n_frames", 1) == 2
    assert result.metadata["duration_ms"] == 1200


def test_thumbnail_renders_png(tmp_path: Path):
    pytest.importorskip("PIL")
    spec = {"title": "Acme", "subtitle": "Notes", "width": 320, "height": 180}
    result = ThumbnailRenderer().render(
        request_for(ArtifactKind.THUMBNAIL, json.dumps(spec).encode(), tmp_path)
    )
    from PIL import Image

    image = Image.open(io.BytesIO(result.content))
    assert image.format == "PNG"
    assert image.size == (320, 180)


def test_invalid_json_reported_clearly(tmp_path: Path):
    with pytest.raises(RenderError, match="not valid JSON"):
        HtmlSlidesRenderer().render(request_for(ArtifactKind.SLIDE_DECK, b"not json", tmp_path))
