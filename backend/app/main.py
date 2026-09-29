"""Punto de entrada de la API (§6). uvicorn la crea con: app.main:create_app --factory"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app import __version__
from app.api import ajustes, alarmas, auth, casas, comandos, eventos, salud, ws
from app.config import Settings, obtener_settings
from app.db import crear_fabrica, crear_motor
from app.logs import configurar_logs
from app.seguridad import Limites, SeguridadApi
from app.services.estado_cache import EstadoCache
from app.services.mqtt_cliente import EstadoMqtt
from app.services.procesador import Procesador
from app.services.ws_hub import HubWs
from app.tareas import tareas_de_fondo
from app.web import CabecerasSeguridad, montar_frontend

ROUTERS = (
    salud.router,
    auth.router,
    casas.router,
    ajustes.router,
    comandos.router,
    alarmas.router,
    eventos.router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with tareas_de_fondo(app):  # ingesta MQTT, vigilante y vencimiento de comandos (§6.2)
        yield
    await app.state.motor.dispose()


async def solicitud_invalida(request: Request, exc: Exception) -> JSONResponse:
    """Errores de validación con el formato de §8: 400 solicitud_invalida, no el 422 de FastAPI."""
    assert isinstance(exc, RequestValidationError)
    campos = sorted(
        {
            ".".join(str(p) for p in error["loc"][1:]) or str(error["loc"][0])
            for error in exc.errors()
        }
    )
    return JSONResponse(
        status_code=400,
        content={
            "detail": {
                "codigo": "solicitud_invalida",
                "mensaje": "Revisa los datos enviados.",
                "campos": campos,
            }
        },
    )


def esquema_openapi(app: FastAPI) -> dict[str, Any]:
    """El OpenAPI de FastAPI, con los errores de validación documentados como 400 (§8)."""
    if app.openapi_schema:
        return app.openapi_schema
    esquema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    error = {"$ref": "#/components/schemas/Error"}
    for operaciones in esquema.get("paths", {}).values():
        for operacion in operaciones.values():
            respuestas = operacion.get("responses", {})
            if respuestas.pop("422", None) is not None:
                respuestas.setdefault(
                    "400",
                    {
                        "description": "Solicitud inválida",
                        "content": {"application/json": {"schema": error}},
                    },
                )
    for nombre in ("HTTPValidationError", "ValidationError"):
        esquema.get("components", {}).get("schemas", {}).pop(nombre, None)
    app.openapi_schema = esquema
    return esquema


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
    app.state.motor = crear_motor(settings.database_url)
    app.state.sesiones = crear_fabrica(app.state.motor)
    app.state.limites = Limites()
    # Viven en memoria del proceso: por eso un solo worker (§6.6)
    app.state.hub = HubWs()
    app.state.mqtt = EstadoMqtt()
    app.state.procesador = Procesador(app.state.sesiones, app.state.hub, EstadoCache())
    app.add_exception_handler(RequestValidationError, solicitud_invalida)
    # Primero la API y el WebSocket; después el frontend y su respaldo SPA (§6.7)
    for router in ROUTERS:
        app.include_router(router, prefix="/api/v1")
    app.include_router(ws.router)
    montar_frontend(app, settings.directorio_frontend)
    app.add_middleware(SeguridadApi, settings=settings, limites=app.state.limites)
    # El último middleware queda por fuera: sus cabeceras cubren también los 403 y 429
    app.add_middleware(CabecerasSeguridad, settings=settings)
    app.openapi = lambda: esquema_openapi(app)  # type: ignore[method-assign]
    return app
