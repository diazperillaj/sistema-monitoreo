"""Ajustes de una casa: recordatorios y avisos (§8.3). Los ve cualquier miembro; los cambia el admin."""

from fastapi import APIRouter

from app.api.casas import obtener_casa
from app.db import Db
from app.schemas.casas import Ajustes, CambioAjustes
from app.schemas.comun import respuestas_error
from app.services.auth import AccesoAdmin, AccesoMiembro

router = APIRouter(prefix="/casas/{casa_id}/ajustes", tags=["casas"])


@router.get("", response_model=Ajustes, responses=respuestas_error(401, 403, 404))
async def ver(acceso: AccesoMiembro, db: Db) -> Ajustes:
    return Ajustes.model_validate(await obtener_casa(db, acceso.casa_id))


@router.patch("", response_model=Ajustes, responses=respuestas_error(400, 401, 403, 404))
async def cambiar(datos: CambioAjustes, acceso: AccesoAdmin, db: Db) -> Ajustes:
    """Cambia solo los campos enviados; un null se ignora."""
    casa = await obtener_casa(db, acceso.casa_id)
    for campo, valor in datos.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(casa, campo, valor)
    await db.commit()
    return Ajustes.model_validate(casa)
