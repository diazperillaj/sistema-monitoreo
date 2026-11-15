"""Canal Web Push (§10.2–§10.4): cifra y envía con pywebpush y clasifica el resultado.

pywebpush es síncrono: cada envío corre en un hilo para no frenar el único worker (§6.6).
Los registros nunca llevan el endpoint completo, solo el servicio (§12.7).
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException, webpush

from app.services.avisos import Aviso

log = logging.getLogger(__name__)
REINTENTOS = 2  # tras el primer intento, ante 429, 5xx o un error de red (§10.4)
ESPERAS_S = (1.0, 3.0)
MAX_FALLOS = 10  # fallos consecutivos antes de borrar la suscripción
ESPERA_ENVIO_S = 10

# Servicios de push de los navegadores: a ningún otro sitio le escribe el backend (evita que
# una suscripción falsa lo use para hacer peticiones a terceros)
SERVICIOS_PUSH = (
    "fcm.googleapis.com",  # Chrome, Edge, Android, Samsung Internet, Opera
    "android.googleapis.com",
    "updates.push.services.mozilla.com",  # Firefox
    "push.apple.com",  # Safari y PWA en iPhone (web.push.apple.com)
    "notify.windows.com",  # Edge antiguo en Windows
)

Entrega = Literal["entregado", "caducada", "fallo", "rechazado"]


def es_servicio_push(endpoint: str) -> bool:
    partes = urlsplit(endpoint)
    host = (partes.hostname or "").lower()
    return partes.scheme == "https" and any(
        host == dominio or host.endswith("." + dominio) for dominio in SERVICIOS_PUSH
    )


def servicio(endpoint: str) -> str:
    """Lo único del endpoint que va a los registros."""
    return urlsplit(endpoint).hostname or "desconocido"


def topic(tag: str) -> str:
    """El header Topic admite hasta 32 caracteres del alfabeto base64url (RFC 8030)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", tag)[:32]


def _publica(vapid: Vapid) -> str:
    return b64urlencode(
        vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    )


def generar_claves() -> tuple[str, str]:
    """Un par VAPID nuevo: (pública, privada), en base64url como las espera el .env."""
    vapid = Vapid()
    vapid.generate_keys()
    privada = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    return _publica(vapid), b64urlencode(privada)


def cargar_vapid(clave_publica: str, clave_privada: str) -> Vapid | None:
    """El par VAPID del .env, o None si falta o no sirve (Web Push queda desactivado).

    Si la pública no corresponde a la privada, el navegador se suscribiría con una y el
    servidor firmaría con otra: todos los envíos fallarían. Mejor detectarlo al arrancar."""
    clave_publica, clave_privada = clave_publica.strip(), clave_privada.strip()
    if not clave_publica or not clave_privada:
        log.warning(
            "Web Push desactivado: faltan VAPID_CLAVE_PUBLICA o VAPID_CLAVE_PRIVADA en el .env "
            "(se crean con: python -m app.cli generar-vapid)"
        )
        return None
    try:
        vapid = Vapid.from_string(clave_privada)
    except Exception:
        log.error("VAPID_CLAVE_PRIVADA no es válida: Web Push queda desactivado")
        return None
    if _publica(vapid) != clave_publica.rstrip("="):
        log.error("VAPID_CLAVE_PUBLICA no corresponde a la privada: Web Push queda desactivado")
        return None
    return vapid


@dataclass(frozen=True)
class Destino:
    """Una suscripción, leída de la base antes de enviar."""

    id: int
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class Resultado:
    suscripcion_id: int
    entrega: Entrega


class CanalWebPush:
    def __init__(
        self, vapid: Vapid | None, sujeto: str, esperas: tuple[float, ...] = ESPERAS_S
    ) -> None:
        self._vapid = vapid
        self._sujeto = sujeto.strip()
        self._esperas = esperas
        if vapid is not None and not self._sujeto:
            log.warning(
                "Web Push desactivado: falta VAPID_SUJETO en el .env (mailto:tu@correo.com)"
            )

    @property
    def activo(self) -> bool:
        """Sin claves VAPID no hay Web Push: la API avisa y no se intenta ningún envío."""
        return self._vapid is not None and bool(self._sujeto)

    async def enviar(self, destinos: list[Destino], aviso: Aviso) -> list[Resultado]:
        if not self.activo or not destinos:
            return []
        datos = json.dumps(aviso.payload(), ensure_ascii=False)
        return list(await asyncio.gather(*(self._entregar(d, datos, aviso) for d in destinos)))

    async def _entregar(self, destino: Destino, datos: str, aviso: Aviso) -> Resultado:
        motivo: object = None
        for intento in range(REINTENTOS + 1):
            try:
                await asyncio.to_thread(self._post, destino, datos, aviso)
                return Resultado(destino.id, "entregado")
            except WebPushException as error:
                codigo = error.status_code
                if codigo in (404, 410):  # la suscripción ya no existe
                    return Resultado(destino.id, "caducada")
                if codigo is not None and codigo != 429 and codigo < 500:
                    # 413 (más de 4 KB) u otro rechazo: reintentar no lo arregla
                    log.error("%s rechazó un push: HTTP %s", servicio(destino.endpoint), codigo)
                    return Resultado(destino.id, "rechazado")
                motivo = codigo
            except requests.RequestException as error:
                motivo = type(error).__name__
            except Exception:
                log.exception("Error al preparar un push para %s", servicio(destino.endpoint))
                return Resultado(destino.id, "rechazado")
            if intento < REINTENTOS:
                await asyncio.sleep(self._esperas[min(intento, len(self._esperas) - 1)])
        log.warning("No se pudo entregar un push a %s (%s)", servicio(destino.endpoint), motivo)
        return Resultado(destino.id, "fallo")

    def _post(self, destino: Destino, datos: str, aviso: Aviso) -> None:
        webpush(
            subscription_info={
                "endpoint": destino.endpoint,
                "keys": {"p256dh": destino.p256dh, "auth": destino.auth},
            },
            data=datos,
            vapid_private_key=self._vapid,
            # Un diccionario nuevo en cada envío: webpush() le agrega aud (el servicio) y exp
            vapid_claims={"sub": self._sujeto},
            ttl=600 if aviso.urgente else 3600,
            headers={"Urgency": "high" if aviso.urgente else "normal", "Topic": topic(aviso.tag)},
            timeout=ESPERA_ENVIO_S,
        )
