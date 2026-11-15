"""WebSocket de una casa (§9): estado en vivo, alarmas, eventos y conexión de la central."""

import json

from fastapi import APIRouter, WebSocket

from app.services.auth import COOKIE, a_usuario_actual, ahora, buscar_sesion, rol_en_casa
from app.services.estado_cache import estado_de_casa

router = APIRouter()

# Códigos de cierre (§9): con ellos el cliente sabe si ir al login o mostrar "sin acceso"
NO_AUTENTICADO = 4401
SIN_PERMISO = 4403


async def rechazo(ws: WebSocket, casa_id: int) -> int | None:
    """El código de cierre si la cookie no abre una sesión vigente de un miembro de la casa."""
    token = ws.cookies.get(COOKIE)
    if not token:
        return NO_AUTENTICADO
    async with ws.app.state.sesiones() as db:
        encontrada = await buscar_sesion(db, token, ahora())
        if encontrada is None:
            return NO_AUTENTICADO
        if await rol_en_casa(db, a_usuario_actual(*encontrada), casa_id) is None:
            return SIN_PERMISO
    return None


def es_ping(texto: str | None) -> bool:
    if not texto or len(texto) > 200:
        return False
    try:
        mensaje = json.loads(texto)
    except ValueError:
        return False
    return isinstance(mensaje, dict) and mensaje.get("tipo") == "ping"


@router.websocket("/ws/v1/casas/{casa_id}")
async def casa_en_vivo(ws: WebSocket, casa_id: int) -> None:
    # Se acepta antes de revisar: si se rechazara el handshake, el navegador solo vería un
    # error genérico, sin el 4401 o 4403 que le dice qué hacer.
    await ws.accept()
    if ws.headers.get("origin") not in ws.app.state.settings.origen_permitido:
        await ws.close(SIN_PERMISO)  # otro sitio no puede abrirlo con la cookie del usuario
        return
    if codigo := await rechazo(ws, casa_id):
        await ws.close(codigo)
        return
    hub = ws.app.state.hub
    # Primero se suscribe y después envía el estado inicial: así no se pierde ninguna alarma ni
    # evento que ocurra entremedio. Si el inicial sale un instante atrasado, el siguiente
    # estado (5 s) lo corrige.
    hub.entrar(casa_id, ws)
    try:
        async with ws.app.state.sesiones() as db:
            estado = await estado_de_casa(db, casa_id, ahora())
        await ws.send_json(
            {"tipo": "estado", "data": estado.model_dump(mode="json", by_alias=True)}
        )
        while True:
            mensaje = await ws.receive()
            if mensaje["type"] == "websocket.disconnect":
                return
            if es_ping(mensaje.get("text")):
                # Con cada ping (25 s) se revisa de nuevo: la sesión pudo cerrarse o el
                # usuario dejar de ser miembro mientras tenía la app abierta.
                if codigo := await rechazo(ws, casa_id):
                    await ws.close(codigo)
                    return
                await ws.send_json({"tipo": "pong"})
    finally:
        hub.salir(casa_id, ws)
