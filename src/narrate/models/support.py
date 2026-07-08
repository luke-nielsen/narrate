"""Small helpers shared by domain models and storage."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime

__all__ = ["new_id", "slugify", "utcnow"]

_SLUG_INVALID = re.compile(r"[^a-z0-9]+")


def new_id() -> str:
    """Return a new opaque entity identifier.

    Identifiers are hex UUID4 strings: unique, URL-safe, and free of
    coordination requirements between processes.
    """
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def slugify(value: str) -> str:
    """Normalise ``value`` into a URL-safe slug.

    Args:
        value: Arbitrary human-entered text.

    Returns:
        Lower-case ASCII with runs of non-alphanumerics collapsed to ``-``.

    Raises:
        ValueError: If nothing slug-worthy remains after normalisation.
    """
    normalised = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_INVALID.sub("-", normalised.lower()).strip("-")
    if not slug:
        msg = f"cannot derive a slug from {value!r}"
        raise ValueError(msg)
    return slug
