"""Constantes y utilidades compartidas por las pruebas."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiomqtt
import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config import Settings
from app.protocolo import EstadoCentral
from app.services.mqtt_cliente import EstadoMqtt

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
RAIZ_REPO = RAIZ_BACKEND.parent
FIXTURES = RAIZ_BACKEND / "tests" / "fixtures"
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


def payload(
    fixture: str = "estado_normal",
    *,
    eventos: list[dict[str, Any]] | None = None,
    **nodos: dict[str, Any],
) -> dict[str, Any]:
    """Un estado de la central (§4.3) de tests/fixtures, con cambios por nodo: n2={"al": 1}."""
    datos = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    for clave, cambios in nodos.items():
        datos["nodos"][int(clave.removeprefix("n"))].update(cambios)
    if eventos is not None:
        datos["eventos"] = eventos
    return datos


def estado(fixture: str = "estado_normal", **cambios: Any) -> EstadoCentral:
    return EstadoCentral.model_validate(payload(fixture, **cambios))


def en_bytes(datos: dict[str, Any]) -> bytes:
    """Como lo publica la central: JSON en UTF-8."""
    return json.dumps(datos, ensure_ascii=False).encode()


class MqttFalso(EstadoMqtt):
    """Conectado y sin broker: guarda lo que se publicaría."""

    def __init__(self) -> None:
        super().__init__(conectado=True)
        self.publicados: list[tuple[str, str]] = []
        self.falla = False

    async def publicar(self, topico: str, carga: str) -> None:
        if self.falla:
            raise aiomqtt.MqttError("se cayó la conexión")
        self.publicados.append((topico, carga))


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
