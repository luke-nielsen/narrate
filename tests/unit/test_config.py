"""Tests for settings resolution."""

from pathlib import Path

import pytest

from narrate.config import NarrateSettings


def test_paths_derive_from_home(tmp_path: Path):
    settings = NarrateSettings(home=tmp_path / "data", _env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.resolved_database_url == f"sqlite:///{tmp_path / 'data' / 'narrate.db'}"
    assert settings.resolved_blobs_dir == tmp_path / "data" / "blobs"
    assert settings.resolved_workspace_dir == tmp_path / "data" / "workspace"


def test_explicit_overrides_win(tmp_path: Path):
    settings = NarrateSettings(
        home=tmp_path,
        database_url="sqlite:///elsewhere.db",
        blobs_dir=tmp_path / "b",
        workspace_dir=tmp_path / "w",
        _env_file=None,  # pyright: ignore[reportCallIssue]
    )
    assert settings.resolved_database_url == "sqlite:///elsewhere.db"
    assert settings.resolved_blobs_dir == tmp_path / "b"
    assert settings.resolved_workspace_dir == tmp_path / "w"


def test_environment_variables_are_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("NARRATE_HOME", str(tmp_path / "env-home"))
    monkeypatch.setenv("NARRATE_DEFAULT_AGENT_NAME", "env-agent")
    settings = NarrateSettings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.home == tmp_path / "env-home"
    assert settings.default_agent_name == "env-agent"


def test_ensure_directories_creates_tree(tmp_path: Path):
    settings = NarrateSettings(home=tmp_path / "fresh", _env_file=None)  # pyright: ignore[reportCallIssue]
    settings.ensure_directories()
    assert settings.resolved_blobs_dir.is_dir()
    assert settings.resolved_workspace_dir.is_dir()
