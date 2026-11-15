"""Migraciones de Alembic sobre PostgreSQL real (§7, §13.2) y restricciones del esquema."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, inspect, make_url, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app import models
from tests.ayudas import Datos, migrar

MOMENTO = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
TABLAS = {tabla.name for tabla in models.Base.metadata.sorted_tables}


@pytest.fixture
async def base_vacia(url_db: str) -> AsyncIterator[str]:
    """Una base aparte en el mismo PostgreSQL, para migrarla sin tocar la de las pruebas."""
    admin = create_async_engine(url_db, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conexion:
        await conexion.execute(text("DROP DATABASE IF EXISTS migraciones WITH (FORCE)"))
        await conexion.execute(text("CREATE DATABASE migraciones"))
    yield make_url(url_db).set(database="migraciones").render_as_string(hide_password=False)
    async with admin.connect() as conexion:
        await conexion.execute(text("DROP DATABASE migraciones WITH (FORCE)"))
    await admin.dispose()


async def en_la_base(url: str, consulta: Callable[[Connection], Any]) -> Any:
    motor = create_async_engine(url)
    try:
        async with motor.connect() as conexion:
            return await conexion.run_sync(consulta)
    finally:
        await motor.dispose()


def diferencias_con_los_modelos(conexion: Connection) -> list[Any]:
    return compare_metadata(MigrationContext.configure(conexion), models.Base.metadata)


def tablas(conexion: Connection) -> set[str]:
    return set(inspect(conexion).get_table_names())


async def test_las_migraciones_suben_bajan_y_coinciden_con_los_modelos(base_vacia: str) -> None:
    await asyncio.to_thread(migrar, base_vacia)
    assert await en_la_base(base_vacia, tablas) == TABLAS | {"alembic_version"}
    assert await en_la_base(base_vacia, diferencias_con_los_modelos) == []

    await asyncio.to_thread(migrar, base_vacia, "base", bajar=True)
    assert await en_la_base(base_vacia, tablas) == {"alembic_version"}

    await asyncio.to_thread(migrar, base_vacia)
    assert await en_la_base(base_vacia, tablas) == TABLAS | {"alembic_version"}


async def test_una_sola_alarma_abierta_por_casa_nodo_y_tipo(db: AsyncSession, datos: Datos) -> None:
    casa = await datos.casa("casa-alarmas")

    def central_caida(**cambios: Any) -> models.Alarma:
        return models.Alarma(
            casa_id=casa_id, nodo_id=None, tipo="CENTRAL_DESCONECTADA", inicio_en=MOMENTO, **cambios
        )

    casa_id = casa.id  # el rollback de abajo invalida los objetos cargados
    db.add(central_caida())
    await db.commit()
    db.add(central_caida())  # nodo_id NULL: NULLS NOT DISTINCT también la hace chocar (§7.3)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

    db.add(central_caida(fin_en=MOMENTO))  # las cerradas no cuentan
    db.add(models.Alarma(casa_id=casa_id, nodo_id=2, tipo="SIN_MOVIMIENTO", inicio_en=MOMENTO))
    await db.commit()


@pytest.mark.parametrize(
    ("modelo", "valores"),
    [
        (models.Usuario, {"email": "Ana@Ejemplo.com", "nombre": "Ana", "clave_hash": "x"}),
        (models.Casa, {"codigo": "Casa-Mayusculas", "nombre": "x"}),
        (models.Casa, {"codigo": "abc", "nombre": "x"}),
        (models.Casa, {"codigo": "casa-ok", "nombre": "x", "recordatorio_min": -1}),
        (models.Casa, {"codigo": "casa-ok", "nombre": "x", "minutos_central_caida": 0}),
    ],
)
async def test_restricciones_check(
    db: AsyncSession, modelo: type[models.Base], valores: dict[str, Any]
) -> None:
    db.add(modelo(**valores))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_rol_de_miembro_solo_admin_o_cuidador(db: AsyncSession, datos: Datos) -> None:
    usuario = await datos.usuario("ana@ejemplo.com")
    casa = await datos.casa("casa-roles")
    db.add(models.Miembro(usuario_id=usuario.id, casa_id=casa.id, rol="invitado"))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
