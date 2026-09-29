"""Comandos de administración (§15.4, §16)."""

import json

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app import models
from app.cli import ErrorCli, crear_casa, crear_superadmin, exportar_openapi, main, reset_clave
from app.config import obtener_settings
from tests.ayudas import URL_SIN_BASE, CrearCliente, Datos, Entrar, ajustes

Sesiones = async_sessionmaker[AsyncSession]


@pytest.fixture
def sesiones(motor: AsyncEngine, db: AsyncSession) -> Sesiones:
    return async_sessionmaker(motor, expire_on_commit=False)


async def test_crear_superadmin_y_entrar(
    sesiones: Sesiones, api: httpx.AsyncClient, entrar: Entrar
) -> None:
    usuario = await crear_superadmin(
        sesiones, " JP@Ejemplo.com ", "Juan Pablo", "una-clave-segura-1"
    )
    assert (usuario.email, usuario.es_superadmin) == ("jp@ejemplo.com", True)
    await entrar(api, "jp@ejemplo.com", "una-clave-segura-1")


async def test_crear_superadmin_valida_la_clave_y_el_email(sesiones: Sesiones) -> None:
    with pytest.raises(ErrorCli, match="al menos 10"):
        await crear_superadmin(sesiones, "jp@ejemplo.com", "JP", "corta")
    await crear_superadmin(sesiones, "jp@ejemplo.com", "JP", "una-clave-segura-1")
    with pytest.raises(ErrorCli, match="Ya existe"):
        await crear_superadmin(sesiones, "JP@ejemplo.com", "Otro", "otra-clave-segura")


async def test_crear_casa_con_su_admin(sesiones: Sesiones, db: AsyncSession, datos: Datos) -> None:
    ana = await datos.usuario("ana@ejemplo.com")
    casa = await crear_casa(
        sesiones, ajustes(), "casa-abuela-x7k2", "Casa de la abuela", "ANA@ejemplo.com"
    )
    rol = await db.scalar(
        select(models.Miembro.rol).where(
            models.Miembro.casa_id == casa.id, models.Miembro.usuario_id == ana.id
        )
    )
    assert rol == "admin"
    assert casa.recordatorio_conexion_min == 60


@pytest.mark.parametrize(
    ("codigo", "admin", "mensaje"),
    [
        ("Casa X", None, "El código"),
        ("casa-abuela-x7k2", "nadie@ejemplo.com", "No existe un usuario"),
    ],
)
async def test_crear_casa_con_errores_no_deja_nada_a_medias(
    sesiones: Sesiones, db: AsyncSession, codigo: str, admin: str | None, mensaje: str
) -> None:
    with pytest.raises(ErrorCli, match=mensaje):
        await crear_casa(sesiones, ajustes(), codigo, "Casa", admin)
    assert await db.scalar(select(func.count()).select_from(models.Casa)) == 0


async def test_crear_casa_repetida(sesiones: Sesiones) -> None:
    await crear_casa(sesiones, ajustes(), "casa-abuela", "Una")
    with pytest.raises(ErrorCli, match="Ya existe"):
        await crear_casa(sesiones, ajustes(), "casa-abuela", "Otra")


async def test_reset_clave(
    sesiones: Sesiones, nuevo_cliente: CrearCliente, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("ana@ejemplo.com")
    celular = nuevo_cliente()
    await entrar(celular, "ana@ejemplo.com")
    temporal = await reset_clave(sesiones, "ana@ejemplo.com")
    assert (await celular.get("/api/v1/auth/yo")).status_code == 401  # cerró todas sus sesiones
    await entrar(nuevo_cliente(), "ana@ejemplo.com", temporal)
    with pytest.raises(ErrorCli):
        await reset_clave(sesiones, "nadie@ejemplo.com")


def test_exportar_openapi() -> None:
    esquema = json.loads(exportar_openapi())
    assert "/api/v1/auth/login" in esquema["paths"]
    assert '"422"' not in json.dumps(esquema["paths"])  # los errores de validación son 400 (§8)


def test_main_termina_con_codigo_1_ante_un_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", URL_SIN_BASE)
    obtener_settings.cache_clear()
    try:
        assert main(["crear-casa", "--codigo", "Casa X", "--nombre", "X"]) == 1
    finally:
        obtener_settings.cache_clear()
    assert "El código" in capsys.readouterr().err
