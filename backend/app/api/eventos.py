"""Bitácora de una casa (§8.5), del evento más reciente al más antiguo."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime
from sqlalchemy import select

from app import models
from app.db import Db
from app.schemas.comun import respuestas_error
from app.schemas.eventos import PaginaEventos, evento_a_esquema
from app.services.auth import AccesoMiembro

router = APIRouter(prefix="/casas/{casa_id}/eventos", tags=["eventos"])


@router.get("", response_model=PaginaEventos, responses=respuestas_error(400, 401, 403, 404))
async def listar(
    acceso: AccesoMiembro,
    db: Db,
    desde: Annotated[AwareDatetime | None, Query(description="ocurrido_en ≥ desde")] = None,
    hasta: Annotated[AwareDatetime | None, Query(description="ocurrido_en < hasta")] = None,
    solo_alarmas: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    antes_de_id: Annotated[int | None, Query(ge=1, description="el `siguiente` anterior")] = None,
) -> PaginaEventos:
    """Paginado por cursor: para la página siguiente se pasa `antes_de_id = siguiente`."""
    evento = models.Evento
    consulta = (
        select(evento, models.Usuario.nombre)
        .outerjoin(models.Usuario, models.Usuario.id == evento.usuario_id)
        .where(evento.casa_id == acceso.casa_id)
    )
    if desde is not None:
        consulta = consulta.where(evento.ocurrido_en >= desde)
    if hasta is not None:
        consulta = consulta.where(evento.ocurrido_en < hasta)
    if solo_alarmas:
        consulta = consulta.where(evento.es_alarma)
    if antes_de_id is not None:
        consulta = consulta.where(evento.id < antes_de_id)
    filas = (await db.execute(consulta.order_by(evento.id.desc()).limit(limit + 1))).all()
    items = [evento_a_esquema(fila, nombre) for fila, nombre in filas[:limit]]
    return PaginaEventos(items=items, siguiente=items[-1].id if len(filas) > limit else None)
