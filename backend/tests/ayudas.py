"""Constantes y utilidades compartidas por las pruebas."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config import Settings

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
RAIZ_REPO = RAIZ_BACKEND.parent
ORIGEN = "https://alarma.test"
CLAVE = "clave-de-prueba-123"
URL_SIN_BASE = "postgresql+asyncpg://nadie@127.0.0.1:9/ninguna"  # nunca responde: pruebas sin base

CrearCliente = Callable[..., httpx.AsyncClient]  # fixtures crear_cliente y nuevo_cliente
Entrar = Callable[..., Awaitable[httpx.Response]]  # fixture entrar


def ajustes(**cambios: Any) -> Settings:
    """Settings de prueba: producción, dominio alarma.test y, si no se indica otra, sin base."""
    valores: dict[str, Any] = {
        "database_url": URL_SIN_BASE,
        "entorno": "produccion",
        "dominio": "alarma.test",
        "origen_permitido": [ORIGEN],
        "directorio_frontend": RAIZ_BACKEND / "sin-build",
    }
    return Settings(**(valores | cambios))


def migrar(url: str, destino: str = "head", *, bajar: bool = False) -> None:
    """Corre Alembic contra `url` (usa asyncio.run: no llamar con un bucle en marcha)."""
    config = Config(str(RAIZ_BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ_BACKEND / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    if bajar:
        command.downgrade(config, destino)
    else:
        command.upgrade(config, destino)


@dataclass
class Datos:
    """Atajos para crear usuarios, casas y membresías directamente en la base."""

    db: AsyncSession
    hash_clave: str  # el de CLAVE, calculado una sola vez

    async def usuario(
        self, email: str, *, nombre: str = "Persona", superadmin: bool = False, activo: bool = True
    ) -> models.Usuario:
        usuario = models.Usuario(
            email=email,
            nombre=nombre,
            clave_hash=self.hash_clave,
            es_superadmin=superadmin,
            activo=activo,
        )
        self.db.add(usuario)
        await self.db.commit()
        return usuario

    async def casa(self, codigo: str, nombre: str | None = None) -> models.Casa:
        casa = models.Casa(codigo=codigo, nombre=nombre or codigo)
        self.db.add(casa)
        await self.db.commit()
        return casa

    async def miembro(self, usuario: models.Usuario, casa: models.Casa, rol: str = "admin") -> None:
        self.db.add(models.Miembro(usuario_id=usuario.id, casa_id=casa.id, rol=rol))
        await self.db.commit()
