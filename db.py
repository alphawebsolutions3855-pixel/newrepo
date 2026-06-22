from sqlmodel import SQLModel, create_engine, Session
from typing import Optional
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)
_ENGINE = None


def _default_database_url() -> str:
    repo_root = Path(__file__).resolve().parent
    return f"sqlite:///{repo_root / 'alpha_automation.db'}"


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        db_url = os.environ.get('AA_DATABASE_URL', _default_database_url())
        # create engine lazily so tests can set env before it's created
        _ENGINE = create_engine(db_url, echo=False)
    return _ENGINE


def init_db():
    # ensure models are imported so metadata is registered
    try:
        import models  # noqa: F401
    except Exception as exc:
        logger.exception('Failed to import models for database initialization')
        raise
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session():
    return Session(get_engine())
