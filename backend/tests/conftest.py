"""Fixtures comunes. Desde F1 se suma PostgreSQL efímero con testcontainers (§13.2)."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.main import create_app

CrearCliente = Callable[..., httpx.AsyncClient]  # fábrica de clientes con ajustes a medida


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
    """Crea clientes HTTP contra una app configurada a medida; los cierra al terminar."""
    clientes: list[httpx.AsyncClient] = []

    def crear(**ajustes: Any) -> httpx.AsyncClient:
        app = create_app(Settings(**ajustes))
        cliente = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clientes.append(cliente)
        return cliente

    yield crear
    for cliente in clientes:
        await cliente.aclose()


@pytest.fixture
def cliente(crear_cliente: CrearCliente, frontend_compilado: Path) -> httpx.AsyncClient:
    """La app en producción, con el build de prueba."""
    return crear_cliente(
        entorno="produccion", dominio="alarma.test", directorio_frontend=frontend_compilado
    )
