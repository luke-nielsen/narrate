"""Application settings.

Settings are resolved from (highest precedence first) explicit keyword
arguments, environment variables prefixed with ``NARRATE_``, an optional
``.env`` file, and finally the defaults below.  All filesystem paths derive
from :attr:`NarrateSettings.home` unless overridden individually, so tests
and multi-tenant setups can relocate the entire data directory with a
single setting.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["NarrateSettings"]

_DEFAULT_HOME = Path.home() / ".narrate"


class NarrateSettings(BaseSettings):
    """Runtime configuration for a Narrate deployment.

    Attributes:
        home: Root directory for all Narrate state.
        database_url: SQLAlchemy database URL.  Defaults to a SQLite
            database inside :attr:`home`.
        blobs_dir: Directory for content-addressed artifact blobs.
        workspace_dir: Scratch directory renderers may use for
            intermediate files (e.g. Remotion project bundles).
        echo_sql: Emit SQL statements to the log (debugging aid).
        default_agent_name: Attribution recorded when a caller does not
            identify itself while claiming tasks or saving artifacts.
    """

    model_config = SettingsConfigDict(
        env_prefix="NARRATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    home: Path = Field(default=_DEFAULT_HOME)
    database_url: str | None = Field(default=None)
    blobs_dir: Path | None = Field(default=None)
    workspace_dir: Path | None = Field(default=None)
    echo_sql: bool = Field(default=False)
    default_agent_name: str = Field(default="unattributed-agent")

    @field_validator("home", mode="after")
    @classmethod
    def _expand_home(cls, value: Path) -> Path:
        """Expand ``~`` and resolve the home directory eagerly."""
        return value.expanduser()

    @property
    def resolved_database_url(self) -> str:
        """Return the effective SQLAlchemy database URL."""
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.home / 'narrate.db'}"

    @property
    def resolved_blobs_dir(self) -> Path:
        """Return the effective blob storage directory."""
        return self.blobs_dir or self.home / "blobs"

    @property
    def resolved_workspace_dir(self) -> Path:
        """Return the effective renderer workspace directory."""
        return self.workspace_dir or self.home / "workspace"

    def ensure_directories(self) -> None:
        """Create all configured directories if they do not exist."""
        for path in (self.home, self.resolved_blobs_dir, self.resolved_workspace_dir):
            path.mkdir(parents=True, exist_ok=True)
