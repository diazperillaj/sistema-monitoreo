"""Qué se notifica y con qué texto (§10.1). FUNCIONES PURAS: arman el Aviso; a quién y por
qué canal lo decide el notificador.

El `tag` agrupa los avisos de un mismo asunto: el celular reemplaza la notificación anterior en
vez de apilarlas (alarma, sus recordatorios y su cierre comparten tag).
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app import models
from app.protocolo import nombre_nodo, texto_alarma

ZONA = ZoneInfo("America/Bogota")  # la hora que se muestra (§3.4)
TIPOS_CONEXION = ("NODO_SIN_CONEXION", "CENTRAL_DESCONECTADA")
TipoAviso = Literal["alarma", "recordatorio", "resuelta", "conexion", "central", "prueba"]


@dataclass(frozen=True)
class Aviso:
    titulo: str
    cuerpo: str
    tag: str
    url: str
    tipo: TipoAviso
    urgente: bool  # alarmas de sensor: Urgency high y TTL corto (§10.2)
    casa_id: int | None
    alarma_id: int | None = None  # solo en los que cuentan como aviso de esa alarma
    nodo_id: int | None = None

    def payload(self) -> dict[str, Any]:
        """El JSON cifrado que recibe el service worker (§10.2)."""
        datos = asdict(self)
        del datos["urgente"]
        return datos


def hora(momento: datetime) -> str:
    return momento.astimezone(ZONA).strftime("%H:%M")


def tag_de(casa_id: int, nodo_id: int | None, tipo_alarma: str) -> str:
    if tipo_alarma == "CENTRAL_DESCONECTADA":
        return f"c-{casa_id}"
    if tipo_alarma == "NODO_SIN_CONEXION":
        return f"n-{casa_id}-{nodo_id}"
    return f"a-{casa_id}-{nodo_id}-{tipo_alarma}"


def _url(casa_id: int) -> str:
    return f"/casa/{casa_id}"


def _texto(alarma: models.Alarma) -> str:
    return texto_alarma(alarma.tipo, alarma.limite_s, alarma.valor)


def alarma_abierta(alarma: models.Alarma, casa: str) -> Aviso:
    """🚨 Una alarma de sensor se abrió."""
    return Aviso(
        titulo=f"🚨 {nombre_nodo(alarma.nodo_id)}",
        cuerpo=f"{_texto(alarma)} · {casa}",
        tag=tag_de(alarma.casa_id, alarma.nodo_id, alarma.tipo),
        url=_url(alarma.casa_id),
        tipo="alarma",
        urgente=True,
        casa_id=alarma.casa_id,
        alarma_id=alarma.id,
        nodo_id=alarma.nodo_id,
    )


def alarma_resuelta(alarma: models.Alarma, usuario: str | None, accion: str | None) -> Aviso:
    """🔕 Una alarma de sensor se cerró (si la casa tiene avisar_resueltas)."""
    if usuario and accion == "desactivar":
        cuerpo = f"{usuario} la desactivó"
    elif usuario:
        cuerpo = f"{usuario} la silenció"
    else:
        cuerpo = "Se normalizó"
    return Aviso(
        titulo=f"🔕 {nombre_nodo(alarma.nodo_id)}",
        cuerpo=cuerpo,
        tag=tag_de(alarma.casa_id, alarma.nodo_id, alarma.tipo),
        url=_url(alarma.casa_id),
        tipo="resuelta",
        urgente=False,
        casa_id=alarma.casa_id,
        nodo_id=alarma.nodo_id,
    )


def nodo_sin_conexion(alarma: models.Alarma, casa: str) -> Aviso:
    """⚠️ Un nodo dejó de reportar (si la casa tiene avisar_nodo_sin_conexion)."""
    return Aviso(
        titulo=f"⚠️ {nombre_nodo(alarma.nodo_id)} sin conexión",
        cuerpo=casa,
        tag=tag_de(alarma.casa_id, alarma.nodo_id, alarma.tipo),
        url=_url(alarma.casa_id),
        tipo="conexion",
        urgente=False,
        casa_id=alarma.casa_id,
        alarma_id=alarma.id,
        nodo_id=alarma.nodo_id,
    )


def central_desconectada(alarma: models.Alarma, casa: str) -> Aviso:
    """📡 La central lleva más de minutos_central_caida sin conexión."""
    return Aviso(
        titulo="📡 Central desconectada",
        cuerpo=f"Sin datos desde las {hora(alarma.inicio_en)} · {casa}",
        tag=tag_de(alarma.casa_id, None, alarma.tipo),
        url=_url(alarma.casa_id),
        tipo="central",
        urgente=False,
        casa_id=alarma.casa_id,
        alarma_id=alarma.id,
    )


def central_en_linea(casa_id: int, casa: str) -> Aviso:
    """✅ Volvió la central, después de haber avisado su caída."""
    return Aviso(
        titulo="✅ Central en línea",
        cuerpo=casa,
        tag=tag_de(casa_id, None, "CENTRAL_DESCONECTADA"),
        url=_url(casa_id),
        tipo="central",
        urgente=False,
        casa_id=casa_id,
    )


def recordatorio(alarma: models.Alarma, casa: str, ahora: datetime) -> Aviso:
    """⏰ La alarma sigue abierta. Reemplaza al aviso anterior de esa alarma (mismo tag)."""
    nodo = nombre_nodo(alarma.nodo_id)
    if alarma.tipo == "CENTRAL_DESCONECTADA":
        titulo, cuerpo = (
            "⏰ Central sigue desconectada",
            f"Desde las {hora(alarma.inicio_en)} · {casa}",
        )
    elif alarma.tipo == "NODO_SIN_CONEXION":
        titulo, cuerpo = (
            f"⏰ Sigue sin conexión: {nodo}",
            f"Desde las {hora(alarma.inicio_en)} · {casa}",
        )
    else:
        minutos = int((ahora - alarma.inicio_en).total_seconds()) // 60
        titulo, cuerpo = f"⏰ Sigue activa: {nodo}", f"{_texto(alarma)} · hace {minutos} min"
    return Aviso(
        titulo=titulo,
        cuerpo=cuerpo,
        tag=tag_de(alarma.casa_id, alarma.nodo_id, alarma.tipo),
        url=_url(alarma.casa_id),
        tipo="recordatorio",
        urgente=alarma.tipo not in TIPOS_CONEXION,
        casa_id=alarma.casa_id,
        alarma_id=alarma.id,
        nodo_id=alarma.nodo_id,
    )


def prueba() -> Aviso:
    """🔔 La que se pide desde el perfil para comprobar un dispositivo."""
    return Aviso(
        titulo="🔔 Notificación de prueba",
        cuerpo="Si ves esto, las alertas llegan a este dispositivo.",
        tag="prueba",
        url="/",
        tipo="prueba",
        urgente=False,
        casa_id=None,
    )
