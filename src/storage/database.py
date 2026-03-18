"""Database connection and session management.

Supports SQLite for the POC and can be switched to PostgreSQL by changing
``DATABASE_URL`` in the environment / ``.env`` file.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DATABASE_URL
from src.storage.models import Base

engine = create_engine(
    DATABASE_URL,
    # SQLite-specific: allow connections from multiple threads (needed for tests)
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    """Return a new SQLAlchemy :class:`~sqlalchemy.orm.Session`.

    The caller is responsible for closing the session.  Prefer
    :func:`session_scope` for automatic cleanup.
    """
    return _SessionLocal()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager that provides a transactional session scope.

    Commits on success, rolls back on exception, and always closes the session.

    Yields
    ------
    Session
        An active SQLAlchemy session.
    """
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all database tables if they do not already exist.

    Safe to call multiple times (idempotent).
    """
    Base.metadata.create_all(bind=engine)
