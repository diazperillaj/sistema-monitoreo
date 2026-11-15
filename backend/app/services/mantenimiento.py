"""Retención de datos (§7.5): lo viejo se borra cada madrugada, por lotes para no bloquear.

Los códigos de Telegram (1 día después de vencer o usarse) se agregan cuando exista su tabla (F4b).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.auth import ahora

log = logging.getLogger(__name__)

LOTE = 5000
HORA = time(3, 0)
ZONA = ZoneInfo("America/Bogota")


@dataclass(frozen=True)
class Regla:
    tabla: str
    condicion: str  # SQL con :limite; nombres fijos, nunca datos del usuario


def reglas(momento: datetime) -> list[tuple[Regla, datetime]]:
    return [
        (Regla("eventos", "ocurrido_en < :limite"), momento - timedelta(days=180)),
        (Regla("lecturas", "medido_en < :limite"), momento - timedelta(days=90)),
        (Regla("sesiones", "expira_en < :limite"), momento),
        # 30 días después de usarse o, si nadie la usó, de vencer
        (
            Regla("invitaciones", "coalesce(usada_en, expira_en) < :limite"),
            momento - timedelta(days=30),
        ),
    ]


async def borrar_por_lotes(
    fabrica: async_sessionmaker[AsyncSession], regla: Regla, limite: datetime, lote: int
) -> int:
    """DELETE ... WHERE ctid IN (SELECT ctid ... LIMIT lote), con un commit por lote: nunca
    bloquea la tabla mucho tiempo, aunque haya meses por borrar."""
    sentencia = text(
        f"DELETE FROM {regla.tabla} WHERE ctid IN "  # tabla y condición son fijas (reglas())
        f"(SELECT ctid FROM {regla.tabla} WHERE {regla.condicion} LIMIT :lote)"
    )
    total = 0
    while True:
        async with fabrica() as db:
            resultado = await db.execute(sentencia, {"limite": limite, "lote": lote})
            await db.commit()
        borradas = resultado.rowcount  # type: ignore[attr-defined]
        total += borradas
        if borradas < lote:
            return total


async def limpiar(
    fabrica: async_sessionmaker[AsyncSession], momento: datetime, lote: int = LOTE
) -> dict[str, int]:
    """Aplica la retención de §7.5. Devuelve cuántas filas borró de cada tabla."""
    borradas = {
        regla.tabla: await borrar_por_lotes(fabrica, regla, limite, lote)
        for regla, limite in reglas(momento)
    }
    log.info(
        "Mantenimiento: %s",
        ", ".join(f"{tabla} {cantidad}" for tabla, cantidad in borradas.items()),
    )
    return borradas


def siguiente(momento: datetime) -> datetime:
    """La próxima madrugada a las 03:00 de Bogotá."""
    local = momento.astimezone(ZONA)
    objetivo = datetime.combine(local.date(), HORA, tzinfo=ZONA)
    if objetivo <= local:
        objetivo += timedelta(days=1)
    return objetivo


async def cada_madrugada(fabrica: async_sessionmaker[AsyncSession]) -> None:
    """Tarea de fondo (§6.2): duerme hasta las 03:00 y limpia. Si falla, lo intenta al día
    siguiente."""

    while True:
        momento = ahora()
        await asyncio.sleep((siguiente(momento) - momento).total_seconds())
        try:
            await limpiar(fabrica, ahora())
        except Exception:
            log.exception("Falló el mantenimiento")
