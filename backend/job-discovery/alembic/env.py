"""
Environnement Alembic.

L'URL n'est pas lue depuis `alembic.ini` mais depuis la configuration de
l'application : la base est décrite par `DATABASE_URL` et par rien d'autre.
C'est ce qui permet de pointer vers Supabase en changeant une seule variable,
sans qu'un fichier versionné contienne jamais un mot de passe.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Toutes les tables doivent être importées pour exister dans les métadonnées.
import app.models  # noqa: F401
from app.config import settings
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", settings.database_url)


def _include(object, name, type_, reflected, compare_to):
    """
    Ce qui ne nous appartient pas ne doit pas entrer dans une migration.

    Sur Supabase, la connexion voit aussi les schémas internes de la
    plateforme (`auth`, `storage`, `realtime`…). Sans ce filtre, un
    autogenerate proposerait de les supprimer.
    """
    if type_ == "table" and getattr(object, "schema", None) not in (None, "public"):
        return False
    return True


def run_migrations_offline() -> None:
    """Produit le SQL sans se connecter — utile pour relire avant d'appliquer."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
