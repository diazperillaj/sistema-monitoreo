"""Fixtures comunes (§13.2): PostgreSQL 17 real y efímero con testcontainers."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app import models
from app.main import create_app
from app.services.auth import hashear_clave
from tests.ayudas import CLAVE, ORIGEN, CrearCliente, Datos, Entrar, ajustes, migrar


def cliente_para(app: FastAPI, origen: str | None = ORIGEN) -> httpx.AsyncClient:
    """Cliente HTTP contra la app, como un navegador en `origen` (None: sin cabecera Origin)."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=ORIGEN,
        headers={"Origin": origen} if origen else None,
    )


# ------------------------------------------------------------- sin base de datos
@pytest.fixture
def frontend_compilado(tmp_path: Path) -> Path:
    """Un build de React mínimo, con la misma forma que frontend/dist."""
    raiz = tmp_path / "frontend"
    (raiz / "assets").mkdir(parents=True)
    (raiz / "icons").mkdir()
    (raiz / "index.html").write_text(
        "<!doctype html><title>Monitoreo del hogar</title>", encoding="utf-8"
    )
    (raiz / "assets" / "index-abc123.js").write_text("console.log('ok')", encoding="utf-8")
    (raiz / "sw.js").write_text("self.addEventListener('push', () => {})", encoding="utf-8")
    (raiz / "manifest.webmanifest").write_text('{"name": "Monitoreo del hogar"}', encoding="utf-8")
    (raiz / "icons" / "icon-192.png").write_bytes(b"\x89PNG\r\n")
    return raiz


@pytest.fixture
async def crear_cliente() -> AsyncIterator[CrearCliente]:
    """Clientes contra apps sin base de datos, configuradas a medida."""
    clientes: list[httpx.AsyncClient] = []

    def crear(**cambios: Any) -> httpx.AsyncClient:
        cliente = cliente_para(create_app(ajustes(**cambios)))
        clientes.append(cliente)
        return cliente

    yield crear
    for cliente in clientes:
        await cliente.aclose()


@pytest.fixture
def cliente(crear_cliente: CrearCliente, frontend_compilado: Path) -> httpx.AsyncClient:
    """La app en producción con el build de prueba y sin base de datos."""
    return crear_cliente(directorio_frontend=frontend_compilado)


# ------------------------------------------------------------- con base de datos
@pytest.fixture(scope="session")
def url_db() -> Iterator[str]:
    """Un PostgreSQL 17 por sesión de pytest, con todas las migraciones aplicadas."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        migrar(url)
        yield url


@pytest.fixture(scope="session")
async def motor(url_db: str) -> AsyncIterator[AsyncEngine]:
    motor = create_async_engine(url_db)
    yield motor
    await motor.dispose()


@pytest.fixture
async def db(motor: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sesión para preparar datos y revisar resultados. Al terminar, vacía todas las tablas."""
    async with AsyncSession(motor, expire_on_commit=False) as sesion:
        yield sesion
    tablas = ", ".join(tabla.name for tabla in models.Base.metadata.sorted_tables)
    async with motor.begin() as conexion:
        await conexion.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def app(url_db: str, db: AsyncSession) -> AsyncIterator[FastAPI]:
    """La app conectada a la base de pruebas, con límites nuevos en cada prueba."""
    app = create_app(ajustes(database_url=url_db))
    yield app
    await app.state.motor.dispose()


@pytest.fixture
async def nuevo_cliente(app: FastAPI) -> AsyncIterator[CrearCliente]:
    """Clientes independientes (cada uno con su cookie) contra la misma app."""
    clientes: list[httpx.AsyncClient] = []

    def crear(origen: str | None = ORIGEN) -> httpx.AsyncClient:
        cliente = cliente_para(app, origen)
        clientes.append(cliente)
        return cliente

    yield crear
    for cliente in clientes:
        await cliente.aclose()


@pytest.fixture
def api(nuevo_cliente: CrearCliente) -> httpx.AsyncClient:
    return nuevo_cliente()


@pytest.fixture(scope="session")
async def hash_de_prueba() -> str:
    return await hashear_clave(CLAVE)  # una sola vez: Argon2 es lento a propósito


@pytest.fixture
def datos(db: AsyncSession, hash_de_prueba: str) -> Datos:
    return Datos(db, hash_de_prueba)


@pytest.fixture
def entrar() -> Entrar:
    """Inicia sesión con `cliente`; la cookie queda guardada en él."""

    async def entrar(cliente: httpx.AsyncClient, email: str, clave: str = CLAVE) -> httpx.Response:
        respuesta = await cliente.post("/api/v1/auth/login", json={"email": email, "clave": clave})
        assert respuesta.status_code == 200, respuesta.text
        return respuesta

    return entrar
