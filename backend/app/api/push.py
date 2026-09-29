"""Web Push: clave pública y suscripciones por dispositivo (§8.7)."""

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app import models
from app.db import Db
from app.schemas.comun import error_api, respuestas_error
from app.schemas.push import BajaSuscripcion, ClavePublica, NuevaSuscripcion
from app.services.auth import Actual

router = APIRouter(prefix="/push", tags=["push"])


@router.get(
    "/clave-publica",
    response_model=ClavePublica,
    responses={503: {"description": "El servidor no tiene claves VAPID"}},
)
async def clave_publica(request: Request) -> ClavePublica:
    """Pública: el navegador la necesita para suscribirse."""
    if not request.app.state.notificador.webpush.activo:
        raise error_api(
            503, "webpush_no_disponible", "El servidor no tiene configuradas las notificaciones."
        )
    return ClavePublica(clave=request.app.state.settings.vapid_clave_publica)


@router.post("/suscripciones", status_code=201, responses=respuestas_error(400, 401, 403))
async def suscribir(datos: NuevaSuscripcion, actual: Actual, request: Request, db: Db) -> Response:
    """Guarda la suscripción de este dispositivo. Si ya existía (otra persona entró en el
    mismo celular), pasa al usuario actual."""
    user_agent = request.headers.get("user-agent")
    sentencia = insert(models.SuscripcionPush).values(
        usuario_id=actual.id,
        endpoint=datos.endpoint,
        p256dh=datos.keys.p256dh,
        auth=datos.keys.auth,
        user_agent=user_agent[:300] if user_agent else None,
    )
    await db.execute(
        sentencia.on_conflict_do_update(
            index_elements=["endpoint"],
            set_={
                "usuario_id": sentencia.excluded.usuario_id,
                "p256dh": sentencia.excluded.p256dh,
                "auth": sentencia.excluded.auth,
                "user_agent": sentencia.excluded.user_agent,
                "fallos_consecutivos": 0,
            },
        )
    )
    await db.commit()
    return Response(status_code=201)


@router.delete("/suscripciones", status_code=204, responses=respuestas_error(400, 401, 403))
async def dar_de_baja(datos: BajaSuscripcion, actual: Actual, db: Db) -> None:
    """Este dispositivo deja de recibir notificaciones. Solo borra una suscripción propia."""
    await db.execute(
        delete(models.SuscripcionPush).where(
            models.SuscripcionPush.endpoint == datos.endpoint,
            models.SuscripcionPush.usuario_id == actual.id,
        )
    )
    await db.commit()
