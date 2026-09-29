"""GET /api/v1/salud (pública, §8.8): la usa el healthcheck de Docker."""

import asyncio
import logging

from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.schemas.salud import Salud

router = APIRouter(tags=["salud"])
log = logging.getLogger(__name__)


async def base_responde(motor: AsyncEngine) -> bool:
    try:
        async with asyncio.timeout(3), motor.connect() as conexion:
            await conexion.execute(text("SELECT 1"))
    except Exception as error:  # cualquier falla cuenta como base caída
        log.warning("La base de datos no responde: %s", type(error).__name__)
        return False
    return True


@router.get(
    "/salud",
    response_model=Salud,
    responses={503: {"model": Salud, "description": "La base de datos no responde"}},
)
async def salud(request: Request, response: Response) -> Salud:
    """Responde 503 si falla la base. MQTT (F2) y Telegram (F4b) no marcan la API como caída."""
    db = "ok" if await base_responde(request.app.state.motor) else "error"
    if db == "error":
        response.status_code = 503
    return Salud(
        ok=db == "ok",
        db=db,
        mqtt="conectado" if getattr(request.app.state, "mqtt_conectado", False) else "desconectado",
        telegram="desactivado",
        version=__version__,
    )
