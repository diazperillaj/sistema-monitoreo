"""CSRF por Origin (§12.3) y límites de intentos en memoria (§12.4).

En memoria alcanza porque la API corre con un solo worker (§6.6).
"""

import ipaddress
import math
import time
from collections.abc import Hashable
from dataclasses import dataclass, field

from fastapi import Request
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings
from app.schemas.comun import error_api

METODOS_NO_SEGUROS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
MENSAJE_LIMITE = "Demasiados intentos. Espera un momento y vuelve a probar."


class Limitador:
    """Cubeta de fichas por clave: `capacidad` fichas que se recargan a razón de `por_segundo`."""

    def __init__(self, capacidad: float, por_segundo: float) -> None:
        self.capacidad = capacidad
        self.por_segundo = por_segundo
        self._cubetas: dict[Hashable, tuple[float, float]] = {}  # clave -> (fichas, cuándo)
        self._tomas = 0

    def tomar(self, clave: Hashable, ahora: float | None = None) -> float:
        """Gasta una ficha. Devuelve 0 si había, o los segundos que faltan para la siguiente."""
        ahora = time.monotonic() if ahora is None else ahora
        fichas, antes = self._cubetas.get(clave, (self.capacidad, ahora))
        fichas = min(self.capacidad, fichas + (ahora - antes) * self.por_segundo)
        if fichas < 1:
            self._cubetas[clave] = (fichas, ahora)
            return (1 - fichas) / self.por_segundo
        self._cubetas[clave] = (fichas - 1, ahora)
        self._tomas += 1
        if self._tomas % 1000 == 0:
            self.podar(ahora)
        return 0.0

    def podar(self, ahora: float) -> None:
        """Olvida las cubetas que ya se llenaron de nuevo: equivalen a no tener registro."""
        llenas = [
            clave
            for clave, (fichas, antes) in self._cubetas.items()
            if fichas + (ahora - antes) * self.por_segundo >= self.capacidad
        ]
        for clave in llenas:
            del self._cubetas[clave]


@dataclass
class Limites:
    """Los límites de §12.4. El de invitaciones se usa en F6 y el de comandos en F3."""

    general: Limitador = field(
        default_factory=lambda: Limitador(40, 10)
    )  # 10/s por IP, ráfaga de 40
    login_email: Limitador = field(
        default_factory=lambda: Limitador(5, 5 / 60)
    )  # 5/min por (IP, email)
    login_ip: Limitador = field(default_factory=lambda: Limitador(20, 20 / 3600))  # 20/h por IP
    invitaciones: Limitador = field(default_factory=lambda: Limitador(10, 10 / 60))  # 10/min por IP
    comandos: Limitador = field(
        default_factory=lambda: Limitador(30, 30 / 60)
    )  # 30/min por usuario


def exigir(limitador: Limitador, clave: Hashable) -> None:
    """Gasta una ficha o responde 429 demasiados_intentos, con Retry-After."""
    espera = limitador.tomar(clave)
    if espera:
        raise error_api(
            429, "demasiados_intentos", MENSAJE_LIMITE, {"Retry-After": str(math.ceil(espera))}
        )


def ip_de(request: Request) -> str | None:
    """IP del cliente. Si la petición llegó por el proxy, uvicorn ya aplicó X-Forwarded-For."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def respuesta_error(estado: int, codigo: str, mensaje: str, **cabeceras: str) -> JSONResponse:
    return JSONResponse(
        {"detail": {"codigo": codigo, "mensaje": mensaje}}, status_code=estado, headers=cabeceras
    )


class SeguridadApi:
    """En /api/*: límite general por IP y, en los métodos no seguros, CSRF por Origin."""

    def __init__(self, app: ASGIApp, settings: Settings, limites: Limites) -> None:
        self.app = app
        self.origenes = frozenset(settings.origen_permitido)
        self.limites = limites

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        cliente = scope.get("client")
        espera = self.limites.general.tomar(cliente[0] if cliente else "desconocida")
        if espera:
            respuesta = respuesta_error(
                429,
                "demasiados_intentos",
                MENSAJE_LIMITE,
                **{"Retry-After": str(math.ceil(espera))},
            )
        elif (
            scope["method"] in METODOS_NO_SEGUROS
            and Headers(scope=scope).get("origin") not in self.origenes
        ):
            # Sin Origin también se rechaza: los navegadores lo mandan siempre en estos métodos
            respuesta = respuesta_error(
                403, "origen_invalido", "El origen de la petición no está permitido."
            )
        else:
            await self.app(scope, receive, send)
            return
        await respuesta(scope, receive, send)
