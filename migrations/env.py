"""Environnement Alembic : l'URL vient de DATABASE_URL, le schéma cible des
modèles SQLAlchemy de concordance.db."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from concordance.db.models import Base
from concordance.db.session import database_url

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata

# `%` est un caractère spécial pour le ConfigParser d'Alembic : il doit être
# doublé, faute de quoi un mot de passe encodé (%40, %2F...) fait échouer
# la migration.
alembic_config.set_main_option("sqlalchemy.url", database_url().replace("%", "%%"))


def run_migrations_offline() -> None:
    """Mode « offline » : émet le SQL sans se connecter à la base."""
    context.configure(
        url=alembic_config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Mode « online » : applique les migrations sur la base."""
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
