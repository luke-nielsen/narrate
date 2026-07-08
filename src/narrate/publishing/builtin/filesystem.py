"""Publish artifacts to a local directory."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from narrate.exceptions import PublishError
from narrate.publishing.base import Publisher, PublishReceipt, PublishRequest

__all__ = ["FileSystemPublisher"]


class FileSystemPublisher(Publisher):
    """Write artifacts into a destination directory.

    The destination string is a directory path; it is created if missing.
    Files are versioned (``name.vN.ext``) so republishing never clobbers
    earlier versions unless ``options["overwrite_latest"]`` also writes an
    unversioned "latest" copy.
    """

    name: ClassVar[str] = "filesystem"
    description: ClassVar[str] = "Copy artifacts into a local directory"

    def publish(self, request: PublishRequest) -> PublishReceipt:
        """Write the artifact to disk.

        Raises:
            PublishError: If the destination cannot be written.
        """
        directory = Path(request.destination).expanduser()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / request.filename
            target.write_bytes(request.content)
            written = [target]
            if request.options.get("overwrite_latest", True):
                latest = directory / request.artifact.name
                latest.write_bytes(request.content)
                written.append(latest)
        except OSError as exc:
            msg = f"cannot write to {request.destination!r}: {exc}"
            raise PublishError(msg) from exc
        return PublishReceipt(
            location=str(written[-1]),
            detail=f"wrote {len(written)} file(s)",
            metadata={"paths": [str(path) for path in written]},
        )
