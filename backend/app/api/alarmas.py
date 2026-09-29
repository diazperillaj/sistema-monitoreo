"""Historial de alarmas de una casa (§8.5), de la más reciente a la más antigua."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime
from sqlalchemy import select

from app import models
from app.db import Db
from app.protocolo import TipoAlarma
from app.schemas.alarmas import PaginaAlarmas, alarma_a_esquema
from app.schemas.comun import respuestas_error
from app.services.auth import AccesoMiembro, ahora

router = APIRouter(prefix="/casas/{casa_id}/alarmas", tags=["alarmas"])


@router.get("", response_model=PaginaAlarmas, responses=respuestas_error(400, 401, 403, 404))
async def listar(
    acceso: AccesoMiembro,
    db: Db,
    abiertas: bool | None = None,
    nodo: Annotated[int | None, Query(ge=0, le=4)] = None,
    tipo: TipoAlarma | None = None,
    desde: Annotated[AwareDatetime | None, Query(description="inicio_en ≥ desde")] = None,
    hasta: Annotated[AwareDatetime | None, Query(description="inicio_en < hasta")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    antes_de_id: Annotated[int | None, Query(ge=1, description="el `siguiente` anterior")] = None,
) -> PaginaAlarmas:
    """Paginado por cursor: para la página siguiente se pasa `antes_de_id = siguiente`."""
    alarma = models.Alarma
    consulta = (
        select(alarma, models.Usuario.nombre)
        .outerjoin(models.Usuario, models.Usuario.id == alarma.cerrada_por_usuario_id)
        .where(alarma.casa_id == acceso.casa_id)
    )
    if abiertas is not None:
        consulta = consulta.where(
            alarma.fin_en.is_(None) if abiertas else alarma.fin_en.is_not(None)
        )
    if nodo is not None:
        consulta = consulta.where(alarma.nodo_id == nodo)
    if tipo is not None:
        consulta = consulta.where(alarma.tipo == tipo)
    if desde is not None:
        consulta = consulta.where(alarma.inicio_en >= desde)
    if hasta is not None:
        consulta = consulta.where(alarma.inicio_en < hasta)
    if antes_de_id is not None:
        consulta = consulta.where(alarma.id < antes_de_id)
    filas = (await db.execute(consulta.order_by(alarma.id.desc()).limit(limit + 1))).all()
    momento = ahora()
    items = [alarma_a_esquema(fila, momento, nombre) for fila, nombre in filas[:limit]]
    return PaginaAlarmas(items=items, siguiente=items[-1].id if len(filas) > limit else None)
