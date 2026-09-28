"""GET /api/v1/salud (pública, §8.8)."""

from fastapi import APIRouter

from app import __version__
from app.schemas.salud import Salud

router = APIRouter(tags=["salud"])


@router.get("/salud", response_model=Salud)
async def salud() -> Salud:
    """Estado de la API. En las fases siguientes suma la base de datos, MQTT y Telegram (§8.8)."""
    return Salud(ok=True, version=__version__)
