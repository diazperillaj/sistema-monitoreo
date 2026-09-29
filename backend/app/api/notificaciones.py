"""Preferencias de notificación del usuario y notificación de prueba (§8.7).

Telegram llega en F4b: hasta entonces figura como no disponible.
"""

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app import models
from app.db import Db
from app.schemas.comun import error_api, respuestas_error
from app.schemas.notificaciones import (
    CambioPreferencias,
    Preferencias,
    PreferenciasTelegram,
    PreferenciasWebPush,
    Prueba,
    ResultadoPrueba,
)
from app.services import avisos
from app.services.auth import Actual

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])
SIN_TELEGRAM = PreferenciasTelegram(
    disponible=False, bot=None, vinculado=False, cuenta=None, vinculado_en=None, activo=False
)


async def _dispositivos(db: Db, usuario_id: int) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(models.SuscripcionPush)
            .where(models.SuscripcionPush.usuario_id == usuario_id)
        )
        or 0
    )


async def _preferencias(db: Db, usuario_id: int) -> Preferencias:
    usuario = await db.get(models.Usuario, usuario_id, populate_existing=True)
    assert usuario is not None  # la sesión es de un usuario activo
    return Preferencias(
        webpush=PreferenciasWebPush(
            activo=usuario.notif_webpush, dispositivos=await _dispositivos(db, usuario_id)
        ),
        telegram=SIN_TELEGRAM,
    )


@router.get("/preferencias", response_model=Preferencias, responses=respuestas_error(401))
async def ver(actual: Actual, db: Db) -> Preferencias:
    return await _preferencias(db, actual.id)


@router.patch(
    "/preferencias", response_model=Preferencias, responses=respuestas_error(400, 401, 403, 409)
)
async def cambiar(datos: CambioPreferencias, actual: Actual, db: Db) -> Preferencias:
    """`webpush: false` pausa las notificaciones en todos sus dispositivos sin borrarlos."""
    if datos.telegram:
        raise error_api(409, "telegram_no_vinculado", "Primero vincula tu cuenta de Telegram.")
    usuario = await db.get(models.Usuario, actual.id)
    assert usuario is not None
    if datos.webpush is not None:
        usuario.notif_webpush = datos.webpush
    await db.commit()
    return await _preferencias(db, actual.id)


@router.post(
    "/prueba",
    status_code=202,
    response_model=ResultadoPrueba,
    responses=respuestas_error(400, 401, 403, 409, 503),
)
async def probar(datos: Prueba, actual: Actual, request: Request, db: Db) -> ResultadoPrueba:
    """Envía "🔔 Notificación de prueba" a los dispositivos del usuario. Responde cuántos."""
    if datos.canal == "telegram":
        raise error_api(409, "telegram_no_disponible", "El servidor no tiene Telegram configurado.")
    notificador = request.app.state.notificador
    if not notificador.webpush.activo:
        raise error_api(
            503, "webpush_no_disponible", "El servidor no tiene configuradas las notificaciones."
        )
    dispositivos = await _dispositivos(db, actual.id)
    if dispositivos:
        notificador.avisar(avisos.prueba(), usuario_id=actual.id)
    return ResultadoPrueba(webpush=dispositivos, telegram=False)
