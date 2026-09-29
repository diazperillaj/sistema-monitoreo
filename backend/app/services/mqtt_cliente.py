"""La conexión del backend con el broker, compartida por la ingesta y los comandos (§6.2, §6.5).

La ingesta abre el cliente y lo deja aquí; los comandos publican por él. Así hay una sola
conexión MQTT por proceso (un solo worker, §6.6).
"""

from dataclasses import dataclass

import aiomqtt

ESPERA_PUBLICACION_S = 5


class MqttNoDisponible(Exception):
    """No hay conexión con el broker en este momento."""


@dataclass
class EstadoMqtt:
    """Lo lee /salud y lo usan los comandos para publicar en casa/<ID>/cmd."""

    conectado: bool = False
    cliente: aiomqtt.Client | None = None

    async def publicar(self, topico: str, carga: str) -> None:
        """QoS 1 y sin retener, como espera la central (§4.2)."""
        if not self.conectado or self.cliente is None:
            raise MqttNoDisponible
        await self.cliente.publish(topico, carga, qos=1, retain=False, timeout=ESPERA_PUBLICACION_S)
