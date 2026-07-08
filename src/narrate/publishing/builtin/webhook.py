"""Publish artifacts by POSTing them to an HTTP endpoint."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import ClassVar

from narrate.exceptions import PublishError
from narrate.publishing.base import Publisher, PublishReceipt, PublishRequest

__all__ = ["WebhookPublisher"]


class WebhookPublisher(Publisher):
    """POST artifact metadata (and optionally content) to a URL.

    The destination is an ``http(s)://`` URL.  The request body is JSON::

        {
          "artifact": {"id": ..., "name": ..., "kind": ..., "version": ...,
                       "media_type": ..., "content_hash": ...},
          "content_base64": "..."   # unless options["include_content"] is false
        }

    Options: ``include_content`` (default true), ``timeout_seconds``
    (default 30), and ``headers`` (extra request headers).
    """

    name: ClassVar[str] = "webhook"
    description: ClassVar[str] = "POST artifacts to an HTTP(S) webhook"

    def publish(self, request: PublishRequest) -> PublishReceipt:
        """Deliver the artifact over HTTP.

        Raises:
            PublishError: If the URL is not HTTP(S) or the request fails.
        """
        if not request.destination.startswith(("http://", "https://")):
            msg = f"webhook destination must be an http(s) URL, got {request.destination!r}"
            raise PublishError(msg)

        payload: dict[str, object] = {
            "artifact": {
                "id": request.artifact.id,
                "name": request.artifact.name,
                "kind": request.artifact.kind.value,
                "version": request.artifact.version,
                "media_type": request.artifact.media_type,
                "content_hash": request.artifact.content_hash,
                "metadata": request.artifact.metadata,
            }
        }
        if request.options.get("include_content", True):
            payload["content_base64"] = base64.b64encode(request.content).decode("ascii")

        headers = {"Content-Type": "application/json"}
        extra_headers = request.options.get("headers", {})
        if isinstance(extra_headers, dict):
            headers.update({str(k): str(v) for k, v in extra_headers.items()})  # pyright: ignore[reportUnknownMemberType]

        http_request = urllib.request.Request(
            request.destination,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        timeout = float(request.options.get("timeout_seconds", 30))
        try:
            with urllib.request.urlopen(http_request, timeout=timeout) as response:
                status = int(response.status)
        except urllib.error.URLError as exc:
            msg = f"webhook delivery to {request.destination} failed: {exc}"
            raise PublishError(msg) from exc
        if status >= 400:  # pragma: no cover - urllib raises for these
            msg = f"webhook returned HTTP {status}"
            raise PublishError(msg)
        return PublishReceipt(
            location=request.destination,
            detail=f"HTTP {status}",
            metadata={"status": status},
        )
