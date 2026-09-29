"""Casas (§8.3). El estado en vivo (GET /casas/{id}/estado) llega en F2."""

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import models
from app.config import Settings
from app.db import Db
from app.schemas.casas import Ajustes, CambioCasa, Casa, CasaNueva, ResumenCasa
from app.schemas.comun import error_api, respuestas_error
from app.services.auth import AccesoAdmin, AccesoMiembro, Actual, Superadmin, casas_visibles

router = APIRouter(prefix="/casas", tags=["casas"])


def casa_nueva(codigo: str, nombre: str, settings: Settings) -> models.Casa:
    """Una casa con los ajustes por defecto del .env (§5.6)."""
    return models.Casa(
        codigo=codigo,
        nombre=nombre,
        recordatorio_min=settings.recordatorio_min_defecto,
        recordatorio_conexion_min=settings.recordatorio_conexion_min_defecto,
        minutos_central_caida=settings.minutos_central_caida_defecto,
    )


def a_esquema(casa: models.Casa) -> Casa:
    return Casa(
        id=casa.id,
        codigo=casa.codigo,
        nombre=casa.nombre,
        creada_en=casa.creada_en,
        ajustes=Ajustes.model_validate(casa),
    )


async def obtener_casa(db: Db, casa_id: int) -> models.Casa:
    casa = await db.get(models.Casa, casa_id)
    if casa is None:
        raise error_api(404, "no_encontrado", "No existe esa casa.")
    return casa


@router.get("", response_model=list[ResumenCasa], responses=respuestas_error(401))
async def listar(actual: Actual, db: Db) -> list[ResumenCasa]:
    """Las casas del usuario, con su conexión y cuántas alarmas tienen abiertas."""
    casas = await casas_visibles(db, actual)
    ids = [casa.id for casa, _ in casas]
    conexion = await db.execute(
        select(models.EstadoActual.casa_id, models.EstadoActual.online).where(
            models.EstadoActual.casa_id.in_(ids)
        )
    )
    alarmas = await db.execute(
        select(models.Alarma.casa_id, func.count())
        .where(models.Alarma.casa_id.in_(ids), models.Alarma.fin_en.is_(None))
        .group_by(models.Alarma.casa_id)
    )
    # .all(): un Result tiene keys() y dict() lo confundiría con un diccionario
    online = {casa_id: en_linea for casa_id, en_linea in conexion.all()}
    abiertas = {casa_id: cantidad for casa_id, cantidad in alarmas.all()}
    return [
        ResumenCasa(
            id=casa.id,
            codigo=casa.codigo,
            nombre=casa.nombre,
            rol=rol,
            online=online.get(casa.id, False),
            alarmas_abiertas=abiertas.get(casa.id, 0),
        )
        for casa, rol in casas
    ]


@router.post(
    "", status_code=201, response_model=Casa, responses=respuestas_error(400, 401, 403, 409)
)
async def crear(datos: CasaNueva, _superadmin: Superadmin, request: Request, db: Db) -> Casa:
    """Registra una casa. Su central necesita además un usuario MQTT (scripts/usuario_mqtt.sh)."""
    en_uso = error_api(409, "codigo_en_uso", "Ya existe una casa con ese código.")
    if await db.scalar(select(models.Casa.id).where(models.Casa.codigo == datos.codigo)):
        raise en_uso
    casa = casa_nueva(datos.codigo, datos.nombre, request.app.state.settings)
    db.add(casa)
    try:
        await db.commit()
    except IntegrityError:  # otra petición la creó al mismo tiempo
        raise en_uso from None
    return a_esquema(casa)


@router.get("/{casa_id}", response_model=Casa, responses=respuestas_error(401, 403, 404))
async def ver(acceso: AccesoMiembro, db: Db) -> Casa:
    return a_esquema(await obtener_casa(db, acceso.casa_id))


@router.patch("/{casa_id}", response_model=Casa, responses=respuestas_error(400, 401, 403, 404))
async def cambiar(datos: CambioCasa, acceso: AccesoAdmin, db: Db) -> Casa:
    casa = await obtener_casa(db, acceso.casa_id)
    if datos.nombre is not None:
        casa.nombre = datos.nombre
    await db.commit()
    return a_esquema(casa)
