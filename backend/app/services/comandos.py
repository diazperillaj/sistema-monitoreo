"""Comandos a la central (§6.5): validar, guardar, publicar, confirmar y vencer.

La API, el service worker (F4) y el bot de Telegram (F4b) los crean con `crear`: así todos
pasan por las mismas validaciones, el mismo límite de intentos y la misma confirmación.
La central no responde con un ACK (§4.5): el comando se confirma cuando un estado posterior
muestra lo que se pidió, y si no llega a tiempo queda sin confirmar.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import aiomqtt
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.protocolo import (
    HAB_PRINCIPAL,
    HAB_SECUNDARIO,
    NODOS,
    VERBOS,
    Accion,
    EstadoCentral,
    sub_valido,
)
from app.schemas.comandos import Comando, comando_a_esquema
from app.schemas.comun import error_api
from app.schemas.eventos import evento_a_esquema
from app.seguridad import Limites, exigir
from app.services.auth import UsuarioActual
from app.services.mqtt_cliente import EstadoMqtt, MqttNoDisponible
from app.services.ws_hub import HubWs

log = logging.getLogger(__name__)
Resueltos = list[tuple[models.Comando, str | None]]  # (comando, nombre de quien lo envió)


# ------------------------------------------------------------------ funciones puras
def payload_cmd(nodo_id: int | None, accion: Accion, sub: int) -> str:
    """El texto de casa/<ID>/cmd (§4.5). Solo lleva valores ya validados, nunca texto del
    usuario (§12.6)."""
    if nodo_id is None:
        if accion != "silenciar" or sub:
            raise ValueError("a todos los nodos solo se les puede silenciar")
        return "todo:silenciar"
    if nodo_id not in NODOS or accion not in VERBOS or not sub_valido(nodo_id, accion, sub):
        raise ValueError(f"comando inválido: {nodo_id}:{accion}:{sub}")
    return f"{nodo_id}:{accion}:{sub}"


def cumple(accion: str, nodo_id: int | None, sub: int, estado: EstadoCentral) -> bool:
    """Predicado de confirmación (§6.5): el estado ya muestra lo que pidió el comando."""
    if nodo_id is None:  # todo:silenciar
        return all(nodo.al == 0 for nodo in estado.nodos if nodo.conocido)
    nodo = estado.nodos[nodo_id]
    if not nodo.conocido:
        return False  # recién reiniciada, la central lo reporta con hab y al en 0: no prueba nada
    if accion == "silenciar":
        return nodo.al == 0
    activo = bool(nodo.hab & (HAB_SECUNDARIO if sub else HAB_PRINCIPAL))
    return activo if accion == "activar" else not activo


def _destino(nodo_id: int | None, sub: int) -> str:
    if nodo_id is None:
        return "todas las alarmas"
    return NODOS[nodo_id] + (" (presencia)" if sub else "")


def texto_enviado(nombre: str, accion: str, nodo_id: int | None, sub: int) -> str:
    """ "Laura silenció Baño": como la bitácora de la central, pero con el nombre (§4.5)."""
    return f"{nombre} {VERBOS[accion]} {_destino(nodo_id, sub)}"


def texto_sin_confirmar(nombre: str | None, accion: str, nodo_id: int | None, sub: int) -> str:
    de = f" de {nombre}" if nombre else ""
    return f"La central no confirmó el comando{de}: {accion} {_destino(nodo_id, sub)}"


def _en_linea(payload: dict[str, Any] | None, nodo_id: int) -> bool:
    if not payload:
        return False
    try:
        return EstadoCentral.model_validate(payload).nodos[nodo_id].en_linea
    except ValidationError:
        return False


# ------------------------------------------------------------------ crear (API, SW y Telegram)
async def crear(
    db: AsyncSession,
    *,
    mqtt: EstadoMqtt,
    hub: HubWs,
    limites: Limites,
    usuario: UsuarioActual,
    casa_id: int,
    nodo_id: int | None,
    accion: Accion,
    sub: int = 0,
) -> Comando:
    """Valida, guarda y publica el comando, y responde sin esperar a la central: la
    confirmación llega con su siguiente estado, o el comando vence (§6.5)."""
    exigir(limites.comandos, usuario.id)  # 30 por minuto por usuario (§12.4)
    carga = payload_cmd(nodo_id, accion, sub)
    fila = (
        await db.execute(
            select(models.Casa.codigo, models.EstadoActual.online, models.EstadoActual.payload)
            .outerjoin(models.EstadoActual, models.EstadoActual.casa_id == models.Casa.id)
            .where(models.Casa.id == casa_id)
        )
    ).first()
    if fila is None:
        raise error_api(404, "no_encontrado", "No existe esa casa.")
    codigo, online, payload = fila
    if not online:
        raise error_api(409, "central_desconectada", "La central está desconectada.")
    if nodo_id is not None and not _en_linea(payload, nodo_id):
        raise error_api(409, "nodo_sin_conexion", "El nodo no tiene conexión.")
    if not mqtt.conectado:
        raise error_api(
            503,
            "mqtt_no_disponible",
            "El servidor perdió la conexión con las centrales. Intenta de nuevo en unos segundos.",
        )

    ahora = datetime.now(UTC)
    comando = models.Comando(
        casa_id=casa_id,
        usuario_id=usuario.id,
        nodo_id=nodo_id,
        accion=accion,
        sub=sub,
        payload=carga,
        estado="pendiente",
        creado_en=ahora,
    )
    evento = models.Evento(
        casa_id=casa_id,
        ocurrido_en=ahora,
        origen="usuario",
        usuario_id=usuario.id,
        nodo_id=nodo_id,
        tipo="comando",
        texto=texto_enviado(usuario.nombre, accion, nodo_id, sub),
        es_alarma=False,
    )
    db.add_all([comando, evento])
    # Se guarda antes de publicar: la central responde en milisegundos, y el procesador debe
    # encontrar el comando para confirmarlo y para atribuirle la alarma que se cierre.
    await db.commit()
    datos = comando_a_esquema(comando, usuario.nombre)
    # El "pendiente" sale antes de publicar para que nunca llegue después del "confirmado"
    await hub.emitir(casa_id, {"tipo": "comando", "data": datos.model_dump(mode="json")})
    await hub.emitir(
        casa_id,
        {
            "tipo": "evento",
            "data": evento_a_esquema(evento, usuario.nombre).model_dump(mode="json"),
        },
    )
    try:
        await mqtt.publicar(f"casa/{codigo}/cmd", carga)
    except (MqttNoDisponible, aiomqtt.MqttError) as error:
        # Sin ACK de la central, un comando que no salió se trata como uno que no se aplicó:
        # vence a los pocos segundos y la app avisa "La central no confirmó el cambio".
        log.warning("No se pudo publicar el comando %s: %s", comando.id, error)
    return datos


# ------------------------------------------------------------------ confirmar y vencer
async def confirmar(
    db: AsyncSession, casa_id: int, estado: EstadoCentral, ahora: datetime
) -> Resueltos:
    """Marca confirmados los comandos pendientes de la casa que este estado ya cumple."""
    confirmados: Resueltos = []
    for comando, nombre in await _pendientes(db, models.Comando.casa_id == casa_id):
        if cumple(comando.accion, comando.nodo_id, comando.sub, estado):
            comando.estado, comando.resuelto_en = "confirmado", ahora
            confirmados.append((comando, nombre))
    return confirmados


async def vencer(db: AsyncSession, limite: datetime, ahora: datetime) -> Resueltos:
    """Marca sin_confirmar los comandos pendientes creados antes de `limite`."""
    vencidos = await _pendientes(db, models.Comando.creado_en < limite)
    for comando, _ in vencidos:
        comando.estado, comando.resuelto_en = "sin_confirmar", ahora
    return vencidos


async def _pendientes(db: AsyncSession, condicion: Any) -> Resueltos:
    filas = await db.execute(
        select(models.Comando, models.Usuario.nombre)
        .outerjoin(models.Usuario, models.Usuario.id == models.Comando.usuario_id)
        .where(models.Comando.estado == "pendiente", condicion)
        .order_by(models.Comando.id)
    )
    return [(comando, nombre) for comando, nombre in filas.all()]
