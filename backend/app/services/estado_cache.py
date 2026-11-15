"""Último estado de cada casa en memoria (§6.1), y el EstadoCasa que ven la API y el WebSocket.

En memoria va lo que el procesador necesita en cada mensaje: el estado anterior (para los
cambios de hab y los eventos nuevos) y cuándo se muestreó por última vez. Tras un reinicio de
la API, el estado anterior se recupera de estado_actual.payload.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.protocolo import EstadoCentral
from app.schemas.alarmas import Alarma, alarma_a_esquema
from app.schemas.estado import EstadoCasa

log = logging.getLogger(__name__)


@dataclass
class CasaEnMemoria:
    casa_id: int
    codigo: str
    previo: EstadoCentral | None = None
    ultimo_muestreo: float | None = None  # reloj monotónico


class EstadoCache:
    def __init__(self) -> None:
        self._por_codigo: dict[str, CasaEnMemoria] = {}

    async def casa(self, db: AsyncSession, codigo: str) -> CasaEnMemoria | None:
        """La casa de una central (codigo = ID_CASA), o None si no está registrada."""
        if codigo in self._por_codigo:
            return self._por_codigo[codigo]
        fila = (
            await db.execute(
                select(models.Casa.id, models.EstadoActual.payload)
                .outerjoin(models.EstadoActual, models.EstadoActual.casa_id == models.Casa.id)
                .where(models.Casa.codigo == codigo)
            )
        ).first()
        if fila is None:
            return None
        casa = CasaEnMemoria(fila.id, codigo, previo=_validar(fila.payload))
        self._por_codigo[codigo] = casa
        return casa


def _validar(payload: dict | None) -> EstadoCentral | None:
    if not payload:
        return None
    try:
        return EstadoCentral.model_validate(payload)
    except ValidationError:
        log.warning("El estado guardado no cumple el contrato actual (§4.3); se ignora")
        return None


async def alarmas_abiertas(db: AsyncSession, casa_id: int, ahora: datetime) -> list[Alarma]:
    filas = await db.execute(
        select(models.Alarma, models.Usuario.nombre)
        .outerjoin(models.Usuario, models.Usuario.id == models.Alarma.cerrada_por_usuario_id)
        .where(models.Alarma.casa_id == casa_id, models.Alarma.fin_en.is_(None))
        .order_by(models.Alarma.inicio_en, models.Alarma.id)
    )
    return [alarma_a_esquema(alarma, ahora, nombre) for alarma, nombre in filas.all()]


async def estado_de_casa(db: AsyncSession, casa_id: int, ahora: datetime) -> EstadoCasa:
    fila = await db.get(models.EstadoActual, casa_id, populate_existing=True)
    recibido = fila.recibido_en if fila else None
    return EstadoCasa(
        casa_id=casa_id,
        online=bool(fila and fila.online),
        online_cambio_en=fila.online_cambio_en if fila else None,
        recibido_en=recibido,
        antiguedad_s=max(0, int((ahora - recibido).total_seconds())) if recibido else None,
        central=_validar(fila.payload) if fila else None,
        alarmas_abiertas=await alarmas_abiertas(db, casa_id, ahora),
    )
