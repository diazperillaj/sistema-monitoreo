"""Entorno de Alembic con la plantilla async (§7): corre las migraciones sobre asyncpg."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def url_de_la_base() -> str:
    """La de sqlalchemy.url si alguien la fijó (las pruebas lo hacen); si no, DATABASE_URL."""
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Falta DATABASE_URL: la arma docker-compose.yml con los valores POSTGRES_*."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=url_de_la_base(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    motor = async_engine_from_config(
        {"sqlalchemy.url": url_de_la_base()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with motor.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await motor.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
