"""Tests for every built-in publisher."""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from narrate.exceptions import PublishError
from narrate.models import Artifact, ArtifactKind
from narrate.publishing.base import PublishRequest
from narrate.publishing.builtin.filesystem import FileSystemPublisher
from narrate.publishing.builtin.static_site import StaticSitePublisher
from narrate.publishing.builtin.webhook import WebhookPublisher


def request_for(destination: str, options: dict[str, Any] | None = None) -> PublishRequest:
    artifact = Artifact(
        project_id="p1",
        kind=ArtifactKind.MARKDOWN,
        name="guide.md",
        version=2,
        media_type="text/markdown",
        content_hash="a" * 64,
        size_bytes=5,
    )
    return PublishRequest(
        artifact=artifact, content=b"hello", destination=destination, options=options or {}
    )


def test_filename_is_version_safe():
    assert request_for("x").filename == "guide.v2.md"


def test_filesystem_writes_versioned_and_latest(tmp_path: Path):
    receipt = FileSystemPublisher().publish(request_for(str(tmp_path / "docs")))
    assert (tmp_path / "docs" / "guide.v2.md").read_bytes() == b"hello"
    assert (tmp_path / "docs" / "guide.md").read_bytes() == b"hello"
    assert receipt.location is not None
    assert len(receipt.metadata["paths"]) == 2


def test_filesystem_can_skip_latest_copy(tmp_path: Path):
    FileSystemPublisher().publish(request_for(str(tmp_path / "docs"), {"overwrite_latest": False}))
    assert not (tmp_path / "docs" / "guide.md").exists()
    assert (tmp_path / "docs" / "guide.v2.md").exists()


def test_static_site_maintains_manifest_and_index(tmp_path: Path):
    publisher = StaticSitePublisher()
    request = request_for(str(tmp_path), {"site_title": "Acme Docs"})
    publisher.publish(request)
    receipt = publisher.publish(request)  # republish the same artifact

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert len(manifest) == 1  # deduplicated by artifact id
    index = (tmp_path / "index.html").read_text()
    assert "guide.md (v2)" in index
    assert (tmp_path / "assets" / "guide.v2.md").exists()
    assert receipt.metadata["entries"] == 1


def test_static_site_rejects_corrupt_manifest(tmp_path: Path):
    (tmp_path / "manifest.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(PublishError, match="corrupt"):
        StaticSitePublisher().publish(request_for(str(tmp_path)))


class _CapturingHandler(BaseHTTPRequestHandler):
    received: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        type(self).received.append(json.loads(self.rfile.read(length)))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: Any) -> None:
        pass  # silence test output


@pytest.fixture
def webhook_server():
    _CapturingHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/hook"
    server.shutdown()


def test_webhook_posts_metadata_and_content(webhook_server: str):
    receipt = WebhookPublisher().publish(request_for(webhook_server))
    assert receipt.metadata["status"] == 200
    payload = _CapturingHandler.received[0]
    assert payload["artifact"]["name"] == "guide.md"
    assert base64.b64decode(payload["content_base64"]) == b"hello"


def test_webhook_can_omit_content(webhook_server: str):
    WebhookPublisher().publish(request_for(webhook_server, {"include_content": False}))
    assert "content_base64" not in _CapturingHandler.received[0]


def test_webhook_rejects_non_http_destination():
    with pytest.raises(PublishError, match="http"):
        WebhookPublisher().publish(request_for("ftp://example.com"))


def test_webhook_connection_failure_raises():
    with pytest.raises(PublishError, match="failed"):
        WebhookPublisher().publish(
            request_for("http://127.0.0.1:1/unreachable", {"timeout_seconds": 0.5})
        )
