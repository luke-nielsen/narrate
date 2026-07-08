"""Publish artifacts into a browsable static documentation site."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, ClassVar

from narrate.exceptions import PublishError
from narrate.publishing.base import Publisher, PublishReceipt, PublishRequest

__all__ = ["StaticSitePublisher"]

_INDEX_STYLE = """
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 3rem auto;
       max-width: 46rem; padding: 0 1rem; color: #111827; }
h1 { margin-bottom: 0.25rem; }
p.tagline { color: #6b7280; margin-top: 0; }
li { margin: 0.5rem 0; }
span.kind { background: #eef2ff; color: #4338ca; border-radius: 0.5rem;
            padding: 0.1rem 0.5rem; font-size: 0.8rem; margin-left: 0.5rem; }
"""


class StaticSitePublisher(Publisher):
    """Maintain a static documentation site in a destination directory.

    Every published artifact is written under ``assets/`` and recorded in
    ``manifest.json``; an ``index.html`` linking all published artifacts
    is regenerated on each publish.  The destination directory can be
    served by any static host (GitHub Pages, S3, nginx...).
    """

    name: ClassVar[str] = "static_site"
    description: ClassVar[str] = "Maintain a browsable static site of published artifacts"

    def publish(self, request: PublishRequest) -> PublishReceipt:
        """Add the artifact to the site and regenerate the index.

        Raises:
            PublishError: If the site directory cannot be written.
        """
        root = Path(request.destination).expanduser()
        try:
            assets = root / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            asset_path = assets / request.filename
            asset_path.write_bytes(request.content)

            manifest = self._load_manifest(root)
            entry = {
                "artifact_id": request.artifact.id,
                "name": request.artifact.name,
                "kind": request.artifact.kind.value,
                "version": request.artifact.version,
                "media_type": request.artifact.media_type,
                "path": f"assets/{request.filename}",
                "created_at": request.artifact.created_at.isoformat(),
            }
            manifest = [e for e in manifest if e.get("artifact_id") != request.artifact.id]
            manifest.append(entry)
            manifest.sort(key=lambda e: (e["kind"], e["name"], e["version"]))
            (root / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

            site_title = str(request.options.get("site_title", "Documentation"))
            (root / "index.html").write_text(
                self._index_html(site_title, manifest), encoding="utf-8"
            )
        except OSError as exc:
            msg = f"cannot write site at {request.destination!r}: {exc}"
            raise PublishError(msg) from exc
        return PublishReceipt(
            location=str(asset_path),
            detail=f"site now lists {len(manifest)} artifact(s)",
            metadata={"index": str(root / "index.html"), "entries": len(manifest)},
        )

    @staticmethod
    def _load_manifest(root: Path) -> list[dict[str, Any]]:
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            return []
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            msg = f"existing manifest at {manifest_path} is corrupt: {exc}"
            raise PublishError(msg) from exc
        return loaded if isinstance(loaded, list) else []

    @staticmethod
    def _index_html(title: str, manifest: list[dict[str, Any]]) -> str:
        items = "".join(
            f"<li><a href='{html.escape(str(entry['path']))}'>"
            f"{html.escape(str(entry['name']))} (v{entry['version']})</a>"
            f"<span class='kind'>{html.escape(str(entry['kind']))}</span></li>"
            for entry in manifest
        )
        return (
            "<!DOCTYPE html>\n"
            f"<html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{_INDEX_STYLE}</style></head>\n"
            f"<body><h1>{html.escape(title)}</h1>"
            "<p class='tagline'>Published by Narrate</p>"
            f"<ul>{items}</ul></body></html>\n"
        )
