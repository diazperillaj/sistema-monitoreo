"""Comandos a la central (§8.4). Responden 202: la confirmación llega por WebSocket (§9)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app import models
from app.db import Db
from app.schemas.comandos import Comando, ComandoNuevo, comando_a_esquema
from app.schemas.comun import error_api, respuestas_error
from app.services import comandos
from app.services.auth import AccesoCasa, AccesoMiembro

router = APIRouter(prefix="/casas/{casa_id}/comandos", tags=["comandos"])
ERRORES_ENVIO = respuestas_error(400, 401, 403, 404, 409, 429, 503)


async def _crear(
    request: Request, db: Db, acceso: AccesoCasa, nodo_id: int | None, accion: str, sub: int
) -> Comando:
    estado = request.app.state
    return await comandos.crear(
        db,
        mqtt=estado.mqtt,
        hub=estado.hub,
        limites=estado.limites,
        usuario=acceso.usuario,
        casa_id=acceso.casa_id,
        nodo_id=nodo_id,
        accion=accion,  # type: ignore[arg-type]  # validada en ComandoNuevo
        sub=sub,
    )


@router.post("", status_code=202, response_model=Comando, responses=ERRORES_ENVIO)
async def enviar(datos: ComandoNuevo, acceso: AccesoMiembro, request: Request, db: Db) -> Comando:
    """Silencia, activa o desactiva un nodo. 409 si la central o el nodo no tienen conexión."""
    return await _crear(request, db, acceso, datos.nodo, datos.accion, datos.sub)


@router.post("/silenciar-todo", status_code=202, response_model=Comando, responses=ERRORES_ENVIO)
async def silenciar_todo(acceso: AccesoMiembro, request: Request, db: Db) -> Comando:
    """Silencia todos los nodos con alarma. Solo exige que la central esté conectada."""
    return await _crear(request, db, acceso, None, "silenciar", 0)


@router.get("", response_model=list[Comando], responses=respuestas_error(400, 401, 403, 404))
async def ultimos(
    acceso: AccesoMiembro, db: Db, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[Comando]:
    """Los últimos comandos de la casa, del más reciente al más antiguo."""
    filas = await db.execute(
        select(models.Comando, models.Usuario.nombre)
        .outerjoin(models.Usuario, models.Usuario.id == models.Comando.usuario_id)
        .where(models.Comando.casa_id == acceso.casa_id)
        .order_by(models.Comando.id.desc())
        .limit(limit)
    )
    return [comando_a_esquema(comando, nombre) for comando, nombre in filas.all()]


@router.get("/{comando_id}", response_model=Comando, responses=respuestas_error(401, 403, 404))
async def ver(comando_id: int, acceso: AccesoMiembro, db: Db) -> Comando:
    fila = (
        await db.execute(
            select(models.Comando, models.Usuario.nombre)
            .outerjoin(models.Usuario, models.Usuario.id == models.Comando.usuario_id)
            .where(models.Comando.id == comando_id, models.Comando.casa_id == acceso.casa_id)
        )
    ).first()
    if fila is None:
        raise error_api(404, "no_encontrado", "No existe ese comando en esta casa.")
    return comando_a_esquema(*fila)
