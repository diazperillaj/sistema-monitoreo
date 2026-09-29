"""Arranque y parada de las tareas de fondo (§6.2). Las usa el lifespan de main.py."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from app.services.mqtt_ingesta import ingesta

log = logging.getLogger(__name__)
VIGILANTE_CADA_S = 10
COMANDOS_CADA_S = 2


async def repetir(nombre: str, cada_s: float, trabajo: Callable[[], Awaitable[None]]) -> None:
    """Ejecuta `trabajo` cada `cada_s` segundos. Si falla, lo registra y sigue."""
    while True:
        try:
            await trabajo()
        except Exception:
            log.exception("Falló la tarea %s", nombre)
        await asyncio.sleep(cada_s)


@asynccontextmanager
async def tareas_de_fondo(app: FastAPI) -> AsyncIterator[None]:
    estado = app.state
    tareas = [
        asyncio.create_task(
            ingesta(estado.settings, estado.procesador, estado.mqtt), name="mqtt_ingesta"
        ),
        asyncio.create_task(
            repetir(
                "vigilante_central", VIGILANTE_CADA_S, estado.procesador.revisar_centrales_caidas
            ),
            name="vigilante_central",
        ),
        asyncio.create_task(
            repetir(
                "comandos_timeout",
                COMANDOS_CADA_S,
                partial(
                    estado.procesador.vencer_comandos,
                    estado.settings.timeout_confirmacion_comando_s,
                ),
            ),
            name="comandos_timeout",
        ),
    ]
    try:
        yield
    finally:
        for tarea in tareas:
            tarea.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
