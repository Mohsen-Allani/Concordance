"""Migrations Alembic contre un vrai PostgreSQL.

Ignoré tant que TEST_POSTGRES_URL n'est pas défini (la CI le définit via un
service PostgreSQL). Ce test vérifie que les migrations produisent exactement
le schéma décrit par les modèles SQLAlchemy.

    TEST_POSTGRES_URL=postgresql+psycopg://user:pwd@localhost:5432/test pytest tests/test_migrations.py
"""

import os

import pytest

URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_POSTGRES_URL non défini")


@pytest.fixture
def postgres(monkeypatch):
    from concordance.db import reset_engine
    monkeypatch.setenv("DATABASE_URL", URL)
    reset_engine()
    yield URL
    reset_engine()


def _alembic():
    from alembic.config import Config

    from concordance import config
    return Config(str(config.ROOT / "alembic.ini"))


def test_migrations_produisent_le_schema_des_modeles(postgres):
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    from concordance.db.models import Base

    cfg = _alembic()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(postgres)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == [], diff


def test_migrations_reversibles(postgres):
    from alembic import command
    cfg = _alembic()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_analyse_enregistree_et_relue_sur_postgres(postgres):
    """JSONB et NUMERIC : aller-retour réel sur la base de production."""
    from decimal import Decimal

    from alembic import command

    from concordance.db import new_session, save_analysis
    from concordance.db.models import Analyse

    from .data import SCENARIO, run_chain, seed_summary

    command.upgrade(_alembic(), "head")
    _, doc_details, comparison = run_chain(SCENARIO)
    id_analyse = save_analysis(seed_summary(comparison), doc_details, comparison, "terminé")
    with new_session() as session:
        a = session.get(Analyse, id_analyse)
        assert a.comparaison["totaux"] == comparison["totaux"]
        bc = next(d for d in a.documents if d.type_document == "BC")
        assert bc.lignes[0].prix_unitaire_ht == Decimal("0.185")
