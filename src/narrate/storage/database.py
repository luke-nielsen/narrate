"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from narrate.storage.orm import Base

__all__ = ["Database"]


class Database:
    """Owns the SQLAlchemy engine and hands out transactional sessions.

    The class is deliberately tiny: repositories receive plain
    :class:`~sqlalchemy.orm.Session` objects, so nothing else in the code
    base depends on how sessions are created.
    """

    def __init__(self, url: str, *, echo: bool = False) -> None:
        """Create the engine.

        Args:
            url: SQLAlchemy database URL.
            echo: Emit SQL to the log for debugging.
        """
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self._engine: Engine = create_engine(url, echo=echo, connect_args=connect_args)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    @property
    def engine(self) -> Engine:
        """The underlying SQLAlchemy engine."""
        return self._engine

    def create_schema(self) -> None:
        """Create all tables that do not already exist."""
        Base.metadata.create_all(self._engine)

    @contextmanager
    def session(self) -> Generator[Session]:
        """Yield a session wrapped in a commit/rollback transaction.

        Commits on success, rolls back on any exception, always closes.
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        """Release all pooled connections."""
        self._engine.dispose()
