"""Cliente MQTT del backend (§6.2): suscribe el estado y la conexión de todas las centrales.

Conecta a mosquitto:1883 como backend_api (red interna de Docker, sin TLS) y reconecta con
espera creciente de 1 a 30 s. Cada mensaje se procesa entero antes de leer el siguiente.
"""

import asyncio
import logging
import re

import aiomqtt

from app.config import Settings
from app.services.mqtt_cliente import EstadoMqtt
from app.services.procesador import Procesador

log = logging.getLogger(__name__)
SUSCRIPCIONES = [("casa/+/estado", 1), ("casa/+/online", 1)]
TOPICO = re.compile(r"casa/([a-z0-9-]{4,40})/(estado|online)")  # ID_CASA según §4.1
ESPERA_MINIMA_S = 1
ESPERA_MAXIMA_S = 30


async def despachar(procesador: Procesador, topico: str, carga: bytes, retenido: bool) -> None:
    coincide = TOPICO.fullmatch(topico)
    if coincide is None:
        log.warning("Tópico MQTT inesperado, ignorado: %s", topico[:100])
        return
    codigo, tipo = coincide.groups()
    if tipo == "estado":
        await procesador.recibir_estado(codigo, carga, retenido)
    else:
        await procesador.recibir_online(codigo, carga, retenido)


async def ingesta(settings: Settings, procesador: Procesador, estado: EstadoMqtt) -> None:
    espera = ESPERA_MINIMA_S
    while True:
        try:
            async with aiomqtt.Client(
                settings.mqtt_host,
                settings.mqtt_puerto,
                username=settings.mqtt_usuario,
                password=settings.mqtt_clave or None,
                identifier="alarma-api",
                keepalive=30,
            ) as cliente:
                await cliente.subscribe(SUSCRIPCIONES)
                estado.conectado, estado.cliente = True, cliente
                espera = ESPERA_MINIMA_S
                log.info("Conectado a MQTT en %s:%s", settings.mqtt_host, settings.mqtt_puerto)
                async for mensaje in cliente.messages:
                    topico = mensaje.topic.value
                    carga = mensaje.payload if isinstance(mensaje.payload, bytes) else b""
                    try:
                        await despachar(procesador, topico, carga, bool(mensaje.retain))
                    except Exception:  # un mensaje que falla no detiene la ingesta
                        log.exception("Error al procesar un mensaje de %s", topico)
        except aiomqtt.MqttError as error:
            log.warning("Sin conexión con MQTT (%s). Reintento en %s s", error, espera)
        except Exception:
            log.exception("Error inesperado en la ingesta MQTT. Reintento en %s s", espera)
        finally:
            estado.conectado, estado.cliente = False, None
        await asyncio.sleep(espera)
        espera = min(espera * 2, ESPERA_MAXIMA_S)
