"""Conexión a PostgreSQL (§7): engine async con asyncpg y sesiones en UTC."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def crear_motor(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        connect_args={"server_settings": {"timezone": "UTC", "application_name": "alarma-api"}},
    )


def crear_fabrica(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Una sesión de base de datos por petición. Cada endpoint confirma con commit()."""
    async with request.app.state.sesiones() as db:
        yield db


Db = Annotated[AsyncSession, Depends(get_session)]
