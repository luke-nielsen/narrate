"""Content-addressed storage for artifact content.

Blobs are stored under ``<root>/<hash[:2]>/<hash>`` keyed by the SHA-256
of their content.  Identical content is therefore deduplicated for free,
and every read can be integrity-checked against its address.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from narrate.exceptions import ArtifactIntegrityError

__all__ = ["BlobStore"]


class BlobStore:
    """Filesystem-backed, content-addressed blob storage."""

    def __init__(self, root: Path) -> None:
        """Initialise the store.

        Args:
            root: Directory that will hold all blobs; created on demand.
        """
        self._root = root

    @property
    def root(self) -> Path:
        """The root directory of the store."""
        return self._root

    @staticmethod
    def digest(content: bytes) -> str:
        """Return the hex SHA-256 digest used to address ``content``."""
        return hashlib.sha256(content).hexdigest()

    def path_for(self, content_hash: str) -> Path:
        """Return the filesystem path where ``content_hash`` is stored."""
        return self._root / content_hash[:2] / content_hash

    def put(self, content: bytes) -> tuple[str, int]:
        """Store ``content`` and return ``(content_hash, size_bytes)``.

        Writing is atomic: content lands in a temporary file first and is
        moved into place, so a crash cannot leave a truncated blob at a
        valid address.  Storing existing content is a no-op.
        """
        content_hash = self.digest(content)
        target = self.path_for(content_hash)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
            tmp_path = Path(tmp_name)
            try:
                with open(fd, "wb") as handle:  # noqa: PTH123 - open(fd) adopts the descriptor
                    handle.write(content)
                tmp_path.replace(target)
            finally:
                tmp_path.unlink(missing_ok=True)
        return content_hash, len(content)

    def get(self, content_hash: str) -> bytes:
        """Read a blob back, verifying integrity.

        Args:
            content_hash: Address returned by :meth:`put`.

        Returns:
            The stored bytes.

        Raises:
            FileNotFoundError: If no blob exists at that address.
            ArtifactIntegrityError: If stored bytes do not hash to
                ``content_hash`` (i.e. on-disk corruption).
        """
        content = self.path_for(content_hash).read_bytes()
        actual = self.digest(content)
        if actual != content_hash:
            msg = f"blob {content_hash} is corrupt (actual hash {actual})"
            raise ArtifactIntegrityError(msg)
        return content

    def exists(self, content_hash: str) -> bool:
        """Return whether a blob exists at ``content_hash``."""
        return self.path_for(content_hash).exists()
