"""Connexion à la base de données.

L'URL est lue dans DATABASE_URL (jamais codée en dur), au premier usage et non
à l'import : importer le paquet ne requiert aucune base, ce qui permet de
lancer les étages du pipeline, le moteur de comparaison et les tests sans
PostgreSQL. Format :

    postgresql+psycopg://utilisateur:motdepasse@localhost:5432/concordance

SQLite est accepté pour les tests (voir tests/conftest.py).
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from concordance import config

_engine: Engine | None = None
_factory: sessionmaker | None = None


def database_url() -> str:
    return config.require_env(
        "DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/concordance")


def _build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:") or ":memory:" in url:
            kwargs["poolclass"] = StaticPool       # une seule base partagée en mémoire
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = _build_engine(database_url())
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def new_session() -> Session:
    """Nouvelle session. À utiliser comme gestionnaire de contexte :

        with new_session() as session, session.begin():
            ...
    """
    get_engine()
    return _factory()


def reset_engine() -> None:
    """Oublie le moteur courant (tests, changement de DATABASE_URL)."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = _factory = None
