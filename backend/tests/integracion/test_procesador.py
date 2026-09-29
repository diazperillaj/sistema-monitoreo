"""Procesamiento de los mensajes de la central (§6.3, §6.4) contra PostgreSQL real."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app import models
from app.db import crear_fabrica
from app.services.estado_cache import EstadoCache
from app.services.procesador import Procesador
from app.services.ws_hub import HubWs
from tests.ayudas import Datos, HubFalso, Reloj, en_bytes, payload

CASA = "casa-dev"


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    return await datos.casa(CASA, "Casa de prueba")


@pytest.fixture
def hub() -> HubFalso:
    return HubFalso()


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


def nuevo_procesador(motor: AsyncEngine, hub: HubWs, reloj: Reloj) -> Procesador:
    return Procesador(
        crear_fabrica(motor), hub, EstadoCache(), reloj=reloj, cronometro=reloj.cronometro
    )


@pytest.fixture
def procesador(motor: AsyncEngine, hub: HubFalso, reloj: Reloj, casa: models.Casa) -> Procesador:
    return nuevo_procesador(motor, hub, reloj)


async def estado_de(procesador: Procesador, fixture: str = "estado_normal", **cambios: Any) -> None:
    await procesador.recibir_estado(CASA, en_bytes(payload(fixture, **cambios)))


async def alarmas(db: AsyncSession) -> list[models.Alarma]:
    consulta = select(models.Alarma).order_by(models.Alarma.id)
    return list((await db.scalars(consulta.execution_options(populate_existing=True))).all())


async def eventos(db: AsyncSession) -> list[models.Evento]:
    consulta = select(models.Evento).order_by(models.Evento.id)
    return list((await db.scalars(consulta.execution_options(populate_existing=True))).all())


async def textos(db: AsyncSession) -> list[str]:
    return [evento.texto for evento in await eventos(db)]


async def fila_estado(db: AsyncSession, casa: models.Casa) -> models.EstadoActual | None:
    return await db.get(models.EstadoActual, casa.id, populate_existing=True)


async def comando(
    db: AsyncSession,
    casa: models.Casa,
    usuario: models.Usuario | None,
    nodo_id: int | None,
    accion: str,
    creado_en: datetime,
) -> None:
    db.add(
        models.Comando(
            casa_id=casa.id,
            usuario_id=usuario.id if usuario else None,
            nodo_id=nodo_id,
            accion=accion,
            sub=0,
            payload="todo:silenciar" if nodo_id is None else f"{nodo_id}:{accion}:0",
            estado="pendiente",
            creado_en=creado_en,
        )
    )
    await db.commit()


# ------------------------------------------------------------------ estado y bitácora
async def test_primer_estado_guarda_estado_conexion_y_bitacora(
    procesador: Procesador, db: AsyncSession, casa: models.Casa, hub: HubFalso, reloj: Reloj
) -> None:
    await estado_de(procesador)

    fila = await fila_estado(db, casa)
    assert fila is not None
    assert fila.payload == payload()
    assert fila.recibido_en == reloj.ahora
    assert fila.online is True
    assert fila.online_cambio_en == reloj.ahora
    # Del más antiguo al más reciente; "Cocina · gas reconectado" lo genera el backend (§6.4)
    assert await textos(db) == [
        "La central se conectó",
        "Central iniciada",
        "App (casa): activó Baño",
    ]
    importados = (await eventos(db))[1:]
    assert {(e.origen, e.tipo, e.es_alarma) for e in importados} == {("central", "central", False)}
    assert await alarmas(db) == []
    assert hub.tipos() == ["central", "evento", "evento", "evento", "estado"]
    assert hub.mensajes[0] == {
        "tipo": "central",
        "online": True,
        "cambio_en": reloj.ahora.isoformat(),
    }


async def test_la_bitacora_de_la_central_no_se_duplica(
    procesador: Procesador, db: AsyncSession
) -> None:
    await estado_de(procesador)
    await estado_de(procesador)
    assert len(await textos(db)) == 3

    nuevo = {"t": "27/09 14:06:00", "x": "App (casa): silenció Baño", "a": False}
    await estado_de(procesador, eventos=[nuevo, *payload()["eventos"]])
    await estado_de(procesador, eventos=[nuevo, *payload()["eventos"]])
    assert (await textos(db))[3:] == ["App (casa): silenció Baño"]


async def test_un_payload_invalido_o_de_otra_casa_se_ignora(
    procesador: Procesador, db: AsyncSession, casa: models.Casa
) -> None:
    await procesador.recibir_estado(CASA, b"{esto no es json")
    incompleto = payload()
    incompleto["nodos"] = incompleto["nodos"][:4]
    await procesador.recibir_estado(CASA, en_bytes(incompleto))
    await procesador.recibir_estado("casa-inexistente", en_bytes(payload()))
    await procesador.recibir_online("casa-inexistente", b"1")

    assert await fila_estado(db, casa) is None
    assert await db.scalar(select(func.count()).select_from(models.EstadoActual)) == 0
    assert await textos(db) == []


# ------------------------------------------------------------------ alarmas de sensor
async def test_alarma_de_sensor_se_abre_una_vez_y_se_cierra_sola(
    procesador: Procesador, db: AsyncSession, hub: HubFalso, reloj: Reloj
) -> None:
    await estado_de(procesador)
    hub.vaciar()

    await estado_de(procesador, "estado_alarma")
    await estado_de(procesador, "estado_alarma")  # la central lo repite cada 5 s
    [alarma] = await alarmas(db)
    assert (alarma.nodo_id, alarma.tipo, alarma.limite_s) == (2, "SIN_MOVIMIENTO", 600)
    assert (alarma.inicio_en, alarma.fin_en) == (reloj.ahora, None)
    ultimo = (await eventos(db))[-1]
    assert (ultimo.texto, ultimo.tipo, ultimo.es_alarma) == (
        "Baño: Sin movimiento por 10 min",
        "alarma",
        True,
    )
    # "ALARMA Baño: ..." de la bitácora de la central no se importa: ya está el del backend
    assert "ALARMA Baño: sin movimiento por 10 min" not in await textos(db)
    assert hub.tipos() == ["alarma:abre", "evento", "estado", "estado"]
    assert hub.mensajes[0]["data"]["texto"] == "Sin movimiento por 10 min"

    hub.vaciar()
    reloj.avanzar(95)
    await estado_de(procesador, "estado_alarma", n2={"al": 0})
    [alarma] = await alarmas(db)
    assert (alarma.fin_en, alarma.cerrada_por, alarma.cerrada_por_usuario_id) == (
        reloj.ahora,
        "central",
        None,
    )
    ultimo = (await eventos(db))[-1]
    assert (ultimo.texto, ultimo.tipo) == (
        "Baño: Sin movimiento por 10 min · se normalizó",
        "alarma_resuelta",
    )
    assert hub.tipos() == ["alarma:cierra", "evento", "estado"]
    assert hub.mensajes[0]["data"]["duracion_s"] == 95
    assert hub.mensajes[-1]["data"]["alarmas_abiertas"] == []


@pytest.mark.parametrize(
    ("nodo_id", "accion", "hace_s", "cerrada_por", "detalle"),
    [
        (2, "silenciar", 5, "usuario", "silenciada por Laura"),
        (None, "silenciar", 5, "usuario", "silenciada por Laura"),  # todo:silenciar
        (2, "desactivar", 5, "usuario", "desactivada por Laura"),
        (2, "silenciar", 16, "central", "se normalizó"),  # fuera de la ventana de 15 s
        (3, "silenciar", 5, "central", "se normalizó"),  # otro nodo
        (2, "activar", 5, "central", "se normalizó"),  # no apaga alarmas
    ],
)
async def test_quien_cerro_la_alarma(
    procesador: Procesador,
    db: AsyncSession,
    datos: Datos,
    casa: models.Casa,
    hub: HubFalso,
    reloj: Reloj,
    nodo_id: int | None,
    accion: str,
    hace_s: int,
    cerrada_por: str,
    detalle: str,
) -> None:
    laura = await datos.usuario("laura@ejemplo.com", nombre="Laura")
    await estado_de(procesador, "estado_alarma")
    reloj.avanzar(30)
    await comando(db, casa, laura, nodo_id, accion, reloj.ahora - timedelta(seconds=hace_s))
    hub.vaciar()

    await estado_de(procesador, "estado_alarma", n2={"al": 0})

    [alarma] = await alarmas(db)
    por_usuario = cerrada_por == "usuario"
    assert alarma.cerrada_por == cerrada_por
    assert alarma.cerrada_por_usuario_id == (laura.id if por_usuario else None)
    ultimo = (await eventos(db))[-1]
    assert ultimo.texto == f"Baño: Sin movimiento por 10 min · {detalle}"
    assert ultimo.usuario_id == (laura.id if por_usuario else None)
    esperado = {"id": laura.id, "nombre": "Laura"} if por_usuario else None
    assert hub.mensajes[0]["data"]["cerrada_por_usuario"] == esperado
    assert hub.mensajes[1]["data"]["usuario"] == esperado


# ------------------------------------------------------------------ conexión de los nodos
async def test_nodo_sin_conexion_no_cierra_sus_otras_alarmas(
    procesador: Procesador, db: AsyncSession, reloj: Reloj
) -> None:
    await estado_de(procesador, n3={"al": 2})  # agua corriendo
    reloj.avanzar(40)
    await estado_de(procesador, n3={"al": 2, "enLinea": False, "hace": 25})

    agua, sin_conexion = await alarmas(db)
    assert (agua.tipo, agua.fin_en) == ("AGUA", None)
    assert sin_conexion.tipo == "NODO_SIN_CONEXION"
    assert sin_conexion.inicio_en == reloj.ahora - timedelta(seconds=25)  # cuando dejó de reportar
    ultimo = (await eventos(db))[-1]
    assert (ultimo.texto, ultimo.tipo, ultimo.es_alarma) == (
        "Cocina · agua perdió la conexión",
        "conexion",
        True,
    )

    reloj.avanzar(60)
    await estado_de(procesador, n3={"al": 0})
    agua, sin_conexion = await alarmas(db)
    assert (sin_conexion.fin_en, sin_conexion.cerrada_por) == (reloj.ahora, "automatica")
    assert (agua.fin_en, agua.cerrada_por) == (reloj.ahora, "central")
    assert (await textos(db))[-2:] == [
        "Cocina · agua volvió a conectarse",
        "Cocina · agua: Agua corriendo más de 8 min · se normalizó",
    ]


async def test_reinicio_de_la_central_no_cierra_alarmas_y_queda_en_la_bitacora(
    procesador: Procesador, db: AsyncSession, reloj: Reloj
) -> None:
    await estado_de(procesador, "estado_alarma")
    reloj.avanzar(60)
    await estado_de(procesador, "estado_reinicio")  # nodos con visto:false y al:0
    reloj.avanzar(5)
    reinicio = payload("estado_reinicio")["eventos"]
    await estado_de(procesador, "estado_alarma", eventos=reinicio)  # los nodos ya reportaron

    [alarma] = await alarmas(db)  # sigue abierta y no se abrió ningún NODO_SIN_CONEXION
    assert (alarma.tipo, alarma.fin_en) == ("SIN_MOVIMIENTO", None)
    assert (await textos(db)).count("Central iniciada") == 1


# ------------------------------------------------------------------ mensajes retenidos
async def test_un_estado_retenido_no_es_un_dato_reciente(
    procesador: Procesador, db: AsyncSession, casa: models.Casa, reloj: Reloj
) -> None:
    await procesador.recibir_estado(CASA, en_bytes(payload()), retenido=True)
    fila = await fila_estado(db, casa)
    assert fila is not None
    assert fila.payload == payload()
    assert (fila.recibido_en, fila.online) == (None, False)  # puede tener horas
    assert await db.scalar(select(func.count()).select_from(models.Lectura)) == 0
    assert "La central se conectó" not in await textos(db)

    reloj.avanzar(3)
    await estado_de(procesador)
    fila = await fila_estado(db, casa)
    assert fila is not None
    assert (fila.recibido_en, fila.online) == (reloj.ahora, True)


async def test_arrancar_con_la_central_ya_caida_abre_la_alarma(
    procesador: Procesador, db: AsyncSession, casa: models.Casa, reloj: Reloj
) -> None:
    """Base nueva y central caída: Mosquitto entrega el estado retenido y después el "0"."""
    await procesador.recibir_estado(CASA, en_bytes(payload()), retenido=True)
    await procesador.recibir_online(CASA, b"0", retenido=True)
    fila = await fila_estado(db, casa)
    assert fila is not None
    assert (fila.online, fila.online_cambio_en) == (False, reloj.ahora)  # la caída cuenta desde ya
    assert (await textos(db))[-1] == "La central se desconectó"

    reloj.avanzar(61)
    await procesador.revisar_centrales_caidas()
    [alarma] = await alarmas(db)
    assert alarma.tipo == "CENTRAL_DESCONECTADA"


async def test_reinicio_del_backend_no_repite_la_bitacora(
    procesador: Procesador, motor: AsyncEngine, db: AsyncSession, hub: HubFalso, reloj: Reloj
) -> None:
    await estado_de(procesador, "estado_alarma", eventos=payload()["eventos"])
    antes = await textos(db)

    otro = nuevo_procesador(motor, hub, reloj)  # memoria vacía: el anterior sale de la base
    datos = payload("estado_alarma", eventos=payload()["eventos"])
    await otro.recibir_estado(CASA, en_bytes(datos), retenido=True)
    assert await textos(db) == antes
    assert len(await alarmas(db)) == 1


# ------------------------------------------------------------------ lecturas
async def test_lecturas_una_por_minuto_y_solo_de_nodos_en_linea(
    procesador: Procesador, db: AsyncSession, reloj: Reloj
) -> None:
    async def lecturas() -> list[tuple[int, str, float]]:
        filas = await db.execute(
            select(models.Lectura.nodo_id, models.Lectura.metrica, models.Lectura.valor).order_by(
                models.Lectura.medido_en, models.Lectura.nodo_id, models.Lectura.metrica
            )
        )
        return [(nodo, metrica, valor) for nodo, metrica, valor in filas.all()]

    await estado_de(procesador)
    primeras = [(3, "caudal", 6.4), (4, "gas", 640.0), (4, "temperatura", 24.6)]
    assert await lecturas() == primeras

    reloj.avanzar(30)
    await estado_de(procesador)
    await procesador.recibir_estado(CASA, en_bytes(payload()), retenido=True)
    assert await lecturas() == primeras  # como máximo una por minuto, y ninguna retenida

    reloj.avanzar(30)
    await estado_de(procesador, n3={"enLinea": False, "hace": 21}, n4={"fl": 66 | 0x10})
    assert await lecturas() == [
        *primeras,
        (4, "temperatura", 24.6),
    ]  # agua sin conexión, MQ calentando


# ------------------------------------------------------------------ horario de la habitación
@pytest.mark.parametrize("con_comando", [False, True])
async def test_habitacion_por_horario(
    procesador: Procesador,
    db: AsyncSession,
    datos: Datos,
    casa: models.Casa,
    reloj: Reloj,
    con_comando: bool,
) -> None:
    await estado_de(procesador)
    if con_comando:
        laura = await datos.usuario("laura@ejemplo.com", nombre="Laura")
        await comando(db, casa, laura, 1, "desactivar", reloj.ahora)
    reloj.avanzar(5)
    await estado_de(procesador, n1={"hab": 0, "fl": 0x40 | 0x04})  # 22:00: FL_HORARIO_NOCTURNO
    reloj.avanzar(8 * 3600)
    await estado_de(procesador)  # 06:00

    horario = [t for t in await textos(db) if t.endswith("(horario)")]
    if con_comando:  # el primer cambio lo explica el comando (ya tiene su propio evento)
        assert horario == ["Habitación activada (horario)"]
    else:
        assert horario == ["Habitación desactivada (horario)", "Habitación activada (horario)"]


# ------------------------------------------------------------------ conexión de la central
async def test_central_desconectada_abre_y_cierra_su_alarma(
    procesador: Procesador, db: AsyncSession, casa: models.Casa, hub: HubFalso, reloj: Reloj
) -> None:
    await procesador.recibir_online(CASA, b"1")
    reloj.avanzar(60)
    se_cayo = reloj.ahora
    hub.vaciar()
    await procesador.recibir_online(CASA, b"0")
    await procesador.recibir_online(CASA, b"0", retenido=True)  # repetido: no cambia nada
    fila = await fila_estado(db, casa)
    assert fila is not None
    assert (fila.online, fila.online_cambio_en) == (False, se_cayo)
    assert hub.tipos() == ["central", "evento"]
    assert hub.mensajes[0] == {"tipo": "central", "online": False, "cambio_en": se_cayo.isoformat()}

    reloj.avanzar(50)
    await procesador.revisar_centrales_caidas()
    assert await alarmas(db) == []  # todavía no pasa minutos_central_caida (1)

    reloj.avanzar(15)
    await procesador.revisar_centrales_caidas()
    await procesador.revisar_centrales_caidas()
    [alarma] = await alarmas(db)
    assert (alarma.nodo_id, alarma.tipo, alarma.inicio_en) == (
        None,
        "CENTRAL_DESCONECTADA",
        se_cayo,
    )
    ultimo = (await eventos(db))[-1]
    assert (ultimo.texto, ultimo.tipo, ultimo.es_alarma) == (
        "Central desconectada desde las 14:06",  # 19:06:10 UTC en Bogotá
        "alarma",
        True,
    )

    reloj.avanzar(120)
    hub.vaciar()
    await procesador.recibir_online(CASA, b"1")
    [alarma] = await alarmas(db)
    assert (alarma.fin_en, alarma.cerrada_por) == (reloj.ahora, "automatica")
    assert (await textos(db))[-1] == "La central volvió a conectarse"
    assert hub.tipos() == ["central", "alarma:cierra", "evento"]
    assert hub.mensajes[1]["data"]["duracion_s"] == 185


async def test_una_caida_corta_no_abre_alarma(
    procesador: Procesador, db: AsyncSession, reloj: Reloj
) -> None:
    await procesador.recibir_online(CASA, b"1")
    await procesador.recibir_online(CASA, b"1", retenido=True)
    await procesador.recibir_online(CASA, b"0")
    reloj.avanzar(20)
    await procesador.recibir_online(CASA, b"1")
    reloj.avanzar(120)
    await procesador.revisar_centrales_caidas()

    assert await alarmas(db) == []
    assert await textos(db) == [
        "La central se conectó",
        "La central se desconectó",
        "La central se conectó",
    ]


async def test_un_estado_en_vivo_corrige_la_conexion(
    procesador: Procesador, db: AsyncSession, casa: models.Casa, reloj: Reloj
) -> None:
    """Si el "1" de la central se perdió, su primer estado en vivo lo corrige."""
    await procesador.recibir_online(CASA, b"0")
    reloj.avanzar(120)
    await procesador.revisar_centrales_caidas()
    reloj.avanzar(5)
    await estado_de(procesador, eventos=[])

    fila = await fila_estado(db, casa)
    assert fila is not None
    assert fila.online is True
    [alarma] = await alarmas(db)
    assert (alarma.fin_en, alarma.cerrada_por) == (reloj.ahora, "automatica")
    assert (await textos(db))[-1] == "La central volvió a conectarse"


async def test_online_con_valor_invalido_se_ignora(
    procesador: Procesador, db: AsyncSession, casa: models.Casa
) -> None:
    await procesador.recibir_online(CASA, b"conectado")
    assert await fila_estado(db, casa) is None


# ------------------------------------------------------------------ comandos (§6.5)
async def comandos_guardados(db: AsyncSession) -> list[models.Comando]:
    consulta = select(models.Comando).order_by(models.Comando.id)
    return list((await db.scalars(consulta.execution_options(populate_existing=True))).all())


async def test_un_estado_confirma_los_comandos_pendientes(
    procesador: Procesador,
    db: AsyncSession,
    datos: Datos,
    casa: models.Casa,
    hub: HubFalso,
    reloj: Reloj,
) -> None:
    laura = await datos.usuario("laura@ejemplo.com", nombre="Laura")
    await estado_de(procesador)
    await comando(db, casa, laura, 2, "desactivar", reloj.ahora)
    await estado_de(procesador)  # todavía con el baño activo
    [pendiente] = await comandos_guardados(db)
    assert pendiente.estado == "pendiente"

    hub.vaciar()
    reloj.avanzar(2)
    await estado_de(procesador, n2={"hab": 0})
    [confirmado] = await comandos_guardados(db)
    assert (confirmado.estado, confirmado.resuelto_en) == ("confirmado", reloj.ahora)
    assert hub.tipos() == ["comando", "estado"]
    assert hub.mensajes[0]["data"]["estado"] == "confirmado"
    assert hub.mensajes[0]["data"]["usuario"] == {"id": laura.id, "nombre": "Laura"}


async def test_los_comandos_vencen_sin_confirmar(
    procesador: Procesador,
    db: AsyncSession,
    datos: Datos,
    casa: models.Casa,
    hub: HubFalso,
    reloj: Reloj,
) -> None:
    laura = await datos.usuario("laura@ejemplo.com", nombre="Laura")
    await comando(db, casa, laura, 2, "silenciar", reloj.ahora)
    reloj.avanzar(5)
    await procesador.vencer_comandos(8)
    assert [c.estado for c in await comandos_guardados(db)] == ["pendiente"]
    assert hub.mensajes == []

    reloj.avanzar(4)
    await procesador.vencer_comandos(8)
    [vencido] = await comandos_guardados(db)
    assert (vencido.estado, vencido.resuelto_en) == ("sin_confirmar", reloj.ahora)
    assert (await textos(db))[-1] == "La central no confirmó el comando de Laura: silenciar Baño"
    assert hub.tipos() == ["evento", "comando"]
    assert hub.mensajes[1]["data"]["estado"] == "sin_confirmar"
