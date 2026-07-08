"""Tests for model support helpers."""

from datetime import UTC

import pytest

from narrate.models.support import new_id, slugify, utcnow


def test_new_id_is_unique_hex():
    first, second = new_id(), new_id()
    assert first != second
    assert len(first) == 32
    int(first, 16)  # parses as hex


def test_utcnow_is_timezone_aware():
    assert utcnow().tzinfo is UTC


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme Notes", "acme-notes"),
        ("  Hello,   World!  ", "hello-world"),
        ("Émigré Café", "emigre-cafe"),
        ("already-a-slug", "already-a-slug"),
        ("UPPER_case mix", "upper-case-mix"),
    ],
)
def test_slugify(raw: str, expected: str):
    assert slugify(raw) == expected


def test_slugify_rejects_unusable_input():
    with pytest.raises(ValueError, match="cannot derive"):
        slugify("!!!")
