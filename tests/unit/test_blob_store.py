"""Tests for the content-addressed blob store."""

from pathlib import Path

import pytest

from narrate.exceptions import ArtifactIntegrityError
from narrate.storage.blob_store import BlobStore


@pytest.fixture
def store(tmp_path: Path) -> BlobStore:
    return BlobStore(tmp_path / "blobs")


def test_put_get_roundtrip(store: BlobStore):
    content = b"hello narrate"
    content_hash, size = store.put(content)
    assert size == len(content)
    assert store.get(content_hash) == content
    assert store.exists(content_hash)


def test_identical_content_is_deduplicated(store: BlobStore):
    first, _ = store.put(b"same bytes")
    second, _ = store.put(b"same bytes")
    assert first == second
    blobs = [p for p in store.root.rglob("*") if p.is_file()]
    assert len(blobs) == 1


def test_sharded_layout(store: BlobStore):
    content_hash, _ = store.put(b"x")
    assert store.path_for(content_hash) == store.root / content_hash[:2] / content_hash


def test_missing_blob_raises(store: BlobStore):
    with pytest.raises(FileNotFoundError):
        store.get("0" * 64)


def test_corrupt_blob_detected(store: BlobStore):
    content_hash, _ = store.put(b"original")
    store.path_for(content_hash).write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        store.get(content_hash)
