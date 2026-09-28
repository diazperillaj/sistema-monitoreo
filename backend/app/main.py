"""Punto de entrada de la API (§6)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import salud
from app.config import Settings, obtener_settings
from app.logs import configurar_logs
from app.web import CabecerasSeguridad, montar_frontend


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Desde F2 aquí arrancan y se detienen las tareas de fondo (app/tareas.py, §6.2).
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or obtener_settings()
    configurar_logs(settings.log_level)
    app = FastAPI(
        title="Monitoreo del hogar",
        version=__version__,
        docs_url="/api/v1/docs",
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    # Primero la API; después el frontend y su respaldo SPA (§6.7)
    app.include_router(salud.router, prefix="/api/v1")
    montar_frontend(app, settings.directorio_frontend)
    app.add_middleware(CabecerasSeguridad, settings=settings)
    return app


app = create_app()
