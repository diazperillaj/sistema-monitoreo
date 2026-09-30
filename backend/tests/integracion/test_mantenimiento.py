"""Retención (§7.5): la tarea de cada madrugada borra lo viejo y deja lo reciente."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app import models
from app.services.mantenimiento import limpiar, siguiente
from tests.ayudas import Datos

AHORA = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)


async def contar(db: AsyncSession, modelo: type[models.Base]) -> int:
    return await db.scalar(select(func.count()).select_from(modelo)) or 0


async def test_borra_lo_viejo_y_deja_lo_reciente(
    datos: Datos, db: AsyncSession, motor: AsyncEngine
) -> None:
    ana = await datos.usuario("ana@ejemplo.com")
    casa = await datos.casa("casa-abuela")

    def evento(dias: int) -> models.Evento:
        return models.Evento(
            casa_id=casa.id,
            ocurrido_en=AHORA - timedelta(days=dias),
            origen="central",
            tipo="info",
            texto=f"hace {dias} días",
        )

    def lectura(dias: int, minuto: int) -> models.Lectura:
        return models.Lectura(
            casa_id=casa.id,
            nodo_id=4,
            metrica="temperatura",
            medido_en=AHORA - timedelta(days=dias, minutes=minuto),
            valor=24.6,
        )

    def sesion(vence_en_dias: int, n: int) -> models.Sesion:
        return models.Sesion(
            usuario_id=ana.id,
            token_hash=f"hash-{n}",
            creada_en=AHORA - timedelta(days=40),
            ultimo_uso_en=AHORA - timedelta(days=10),
            expira_en=AHORA + timedelta(days=vence_en_dias),
        )

    def invitacion(
        n: int, vence_en_dias: int, usada_hace_dias: int | None = None
    ) -> models.Invitacion:
        return models.Invitacion(
            casa_id=casa.id,
            rol="cuidador",
            token_hash=f"invitacion-{n}",
            creada_en=AHORA - timedelta(days=60),
            expira_en=AHORA + timedelta(days=vence_en_dias),
            usada_en=None if usada_hace_dias is None else AHORA - timedelta(days=usada_hace_dias),
        )

    db.add_all(
        [evento(200), evento(181), evento(179), evento(1)]
        + [lectura(95, m) for m in range(3)]
        + [lectura(89, 0), lectura(0, 1)]
        + [sesion(-1, 1), sesion(-5, 2), sesion(3, 3)]
        + [
            invitacion(1, -40),  # venció hace 40 días: se borra
            invitacion(2, -10),  # venció hace 10: todavía no
            invitacion(3, 2, usada_hace_dias=31),  # se usó hace 31: se borra
            invitacion(4, 2),  # vigente
        ]
    )
    await db.commit()

    # Lotes de 1: así se prueba también el borrado por lotes
    borradas = await limpiar(async_sessionmaker(motor), AHORA, lote=1)

    assert borradas == {"eventos": 2, "lecturas": 3, "sesiones": 2, "invitaciones": 2}
    assert await contar(db, models.Evento) == 2
    assert await contar(db, models.Lectura) == 2
    assert await contar(db, models.Sesion) == 1
    quedan = (
        await db.scalars(select(models.Invitacion.token_hash).order_by(models.Invitacion.id))
    ).all()
    assert quedan == ["invitacion-2", "invitacion-4"]


def test_corre_cada_madrugada_a_las_3_de_bogota() -> None:
    # 07:00 UTC son las 02:00 en Bogotá: falta una hora
    assert siguiente(datetime(2026, 9, 30, 7, 0, tzinfo=UTC)) == datetime(
        2026, 9, 30, 8, 0, tzinfo=UTC
    )
    # Justo a las 03:00, o más tarde, ya es la del día siguiente
    assert siguiente(datetime(2026, 9, 30, 8, 0, tzinfo=UTC)) == datetime(
        2026, 10, 1, 8, 0, tzinfo=UTC
    )
    assert siguiente(datetime(2026, 9, 30, 20, 0, tzinfo=UTC)) == datetime(
        2026, 10, 1, 8, 0, tzinfo=UTC
    )
