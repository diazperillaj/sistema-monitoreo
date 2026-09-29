"""Qué se notifica, a quién y cuándo (§10.1), con el procesador real y un canal sin red."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app import models
from app.db import crear_fabrica
from app.services.estado_cache import EstadoCache
from app.services.notificador import Notificador
from app.services.procesador import Procesador
from tests.ayudas import CanalFalso, Datos, HubFalso, Reloj, en_bytes, payload

CASA = "casa-dev"


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def canal() -> CanalFalso:
    return CanalFalso()


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    return await datos.casa(CASA, "Casa de la abuela")


@pytest.fixture
def notificador(motor: AsyncEngine, canal: CanalFalso, reloj: Reloj) -> Notificador:
    return Notificador(crear_fabrica(motor), canal, reloj=reloj)


@pytest.fixture
def procesador(
    motor: AsyncEngine, notificador: Notificador, reloj: Reloj, casa: models.Casa
) -> Procesador:
    return Procesador(
        crear_fabrica(motor),
        HubFalso(),
        EstadoCache(),
        reloj=reloj,
        cronometro=reloj.cronometro,
        notificador=notificador,
    )


@pytest.fixture
async def ana(datos: Datos, casa: models.Casa) -> models.SuscripcionPush:
    """Miembro de la casa con un celular suscrito."""
    usuario = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    await datos.miembro(usuario, casa, "cuidador")
    return await datos.suscripcion(usuario)


async def estado(
    procesador: Procesador, notificador: Notificador, fixture: str = "estado_normal", **cambios: Any
) -> None:
    await procesador.recibir_estado(CASA, en_bytes(payload(fixture, **cambios)))
    await notificador.esperar()


async def ajustar(db: AsyncSession, casa: models.Casa, **ajustes: Any) -> None:
    for campo, valor in ajustes.items():
        setattr(casa, campo, valor)
    await db.commit()


# ------------------------------------------------------------------ destinatarios
async def test_una_alarma_llega_a_cada_dispositivo_de_los_miembros_con_web_push(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    datos: Datos,
    casa: models.Casa,
    db: AsyncSession,
    reloj: Reloj,
) -> None:
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    beto = await datos.usuario("beto@ejemplo.com")  # pausó Web Push
    beto.notif_webpush = False
    carla = await datos.usuario("carla@ejemplo.com")  # no es de esta casa
    dani = await datos.usuario("dani@ejemplo.com", activo=False)
    for usuario in (ana, beto, dani):
        await datos.miembro(usuario, casa, "cuidador")
    celular, tableta = await datos.suscripcion(ana), await datos.suscripcion(ana)
    for usuario in (beto, carla, dani):
        await datos.suscripcion(usuario)

    await estado(procesador, notificador)
    await estado(procesador, notificador, "estado_alarma")
    await estado(procesador, notificador, "estado_alarma")  # repetido: no se avisa otra vez

    [(aviso, destinos)] = canal.envios
    assert (aviso.titulo, aviso.cuerpo) == (
        "🚨 Baño",
        "Sin movimiento por 10 min · Casa de la abuela",
    )
    assert sorted(d.id for d in destinos) == sorted([celular.id, tableta.id])
    alarma = await db.scalar(select(models.Alarma).execution_options(populate_existing=True))
    assert alarma is not None
    assert (alarma.avisos_enviados, alarma.ultimo_aviso_en) == (1, reloj.ahora)


# ------------------------------------------------------------------ cierres y conexión
@pytest.mark.parametrize("avisar_resueltas", [True, False])
async def test_alarma_resuelta_segun_el_ajuste(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    ana: models.SuscripcionPush,
    casa: models.Casa,
    db: AsyncSession,
    avisar_resueltas: bool,
) -> None:
    await ajustar(db, casa, avisar_resueltas=avisar_resueltas)
    await estado(procesador, notificador, "estado_alarma")
    await estado(procesador, notificador, "estado_alarma", n2={"al": 0})
    esperados = ["🚨 Baño", "🔕 Baño"] if avisar_resueltas else ["🚨 Baño"]
    assert canal.titulos() == esperados
    if avisar_resueltas:
        resuelta = canal.envios[1][0]
        assert (resuelta.cuerpo, resuelta.tag) == ("Se normalizó", canal.envios[0][0].tag)


@pytest.mark.parametrize("avisar_nodo", [True, False])
async def test_nodo_sin_conexion_segun_el_ajuste(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    ana: models.SuscripcionPush,
    casa: models.Casa,
    db: AsyncSession,
    avisar_nodo: bool,
) -> None:
    await ajustar(db, casa, avisar_nodo_sin_conexion=avisar_nodo)
    await estado(procesador, notificador)
    await estado(procesador, notificador, n3={"enLinea": False, "hace": 25})
    await estado(procesador, notificador)  # vuelve: no hay aviso de vuelta (§10.1)
    assert canal.titulos() == (["⚠️ Cocina · agua sin conexión"] if avisar_nodo else [])


async def test_central_desconectada_y_de_nuevo_en_linea(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    ana: models.SuscripcionPush,
    reloj: Reloj,
) -> None:
    await procesador.recibir_online(CASA, b"1")
    await procesador.recibir_online(CASA, b"0")
    reloj.avanzar(65)
    await procesador.revisar_centrales_caidas()
    await notificador.esperar()
    reloj.avanzar(30)
    await procesador.recibir_online(CASA, b"1")
    await notificador.esperar()
    assert canal.titulos() == ["📡 Central desconectada", "✅ Central en línea"]
    assert canal.envios[0][0].cuerpo == "Sin datos desde las 14:05 · Casa de la abuela"


async def test_una_caida_corta_no_avisa_nada(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    ana: models.SuscripcionPush,
    reloj: Reloj,
) -> None:
    await procesador.recibir_online(CASA, b"1")
    await procesador.recibir_online(CASA, b"0")
    reloj.avanzar(20)
    await procesador.recibir_online(CASA, b"1")
    reloj.avanzar(120)
    await procesador.revisar_centrales_caidas()
    await notificador.esperar()
    assert canal.envios == []


# ------------------------------------------------------------------ recordatorios
async def recordatorios(procesador: Procesador, notificador: Notificador) -> None:
    await procesador.revisar_recordatorios()
    await notificador.esperar()


async def test_recordatorio_de_sensor_cada_recordatorio_min(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    ana: models.SuscripcionPush,
    db: AsyncSession,
    reloj: Reloj,
) -> None:
    await estado(procesador, notificador, "estado_alarma")  # recordatorio_min = 5
    reloj.avanzar(4 * 60 + 50)
    await recordatorios(procesador, notificador)
    reloj.avanzar(10)
    await recordatorios(procesador, notificador)
    reloj.avanzar(60)
    await recordatorios(procesador, notificador)  # el siguiente, a los 10 min
    reloj.avanzar(4 * 60)
    await recordatorios(procesador, notificador)
    assert canal.titulos() == ["🚨 Baño", "⏰ Sigue activa: Baño", "⏰ Sigue activa: Baño"]
    assert [aviso.cuerpo for aviso, _ in canal.envios[1:]] == [
        "Sin movimiento por 10 min · hace 5 min",
        "Sin movimiento por 10 min · hace 10 min",
    ]
    alarma = await db.scalar(select(models.Alarma).execution_options(populate_existing=True))
    assert alarma is not None
    assert alarma.avisos_enviados == 3


async def test_recordatorio_en_cero_no_se_envia(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    ana: models.SuscripcionPush,
    casa: models.Casa,
    db: AsyncSession,
    reloj: Reloj,
) -> None:
    await ajustar(db, casa, recordatorio_min=0)
    await estado(procesador, notificador, "estado_alarma")
    reloj.avanzar(3600)
    await recordatorios(procesador, notificador)
    assert canal.titulos() == ["🚨 Baño"]


@pytest.mark.parametrize("avisar_nodo", [True, False])
async def test_recordatorios_de_conexion_cada_recordatorio_conexion_min(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    ana: models.SuscripcionPush,
    casa: models.Casa,
    db: AsyncSession,
    reloj: Reloj,
    avisar_nodo: bool,
) -> None:
    await ajustar(db, casa, avisar_nodo_sin_conexion=avisar_nodo)
    await estado(procesador, notificador, n3={"enLinea": False, "hace": 25})
    await procesador.recibir_online(CASA, b"0")
    reloj.avanzar(70)
    await procesador.revisar_centrales_caidas()
    await notificador.esperar()
    canal.envios.clear()

    reloj.avanzar(58 * 60)  # la del nodo empezó hace 59 min y el aviso de la central, hace 58
    await recordatorios(procesador, notificador)
    assert canal.envios == []
    reloj.avanzar(2 * 60)
    await recordatorios(procesador, notificador)
    esperados = ["⏰ Sigue sin conexión: Cocina · agua", "⏰ Central sigue desconectada"]
    assert canal.titulos() == (esperados if avisar_nodo else esperados[1:])


# ------------------------------------------------------------------ resultado del envío
async def test_el_resultado_de_cada_envio_queda_en_la_suscripcion(
    procesador: Procesador,
    notificador: Notificador,
    canal: CanalFalso,
    datos: Datos,
    casa: models.Casa,
    db: AsyncSession,
    reloj: Reloj,
) -> None:
    ana = await datos.usuario("ana@ejemplo.com")
    await datos.miembro(ana, casa, "cuidador")
    sana = await datos.suscripcion(ana, fallos_consecutivos=3)
    caducada = await datos.suscripcion(ana)
    fallando = await datos.suscripcion(ana)
    a_punto = await datos.suscripcion(ana, fallos_consecutivos=9)
    canal.respuestas = {
        caducada.endpoint: "caducada",
        fallando.endpoint: "fallo",
        a_punto.endpoint: "fallo",
    }

    await estado(procesador, notificador, "estado_alarma")

    filas = await db.execute(
        select(
            models.SuscripcionPush.id,
            models.SuscripcionPush.fallos_consecutivos,
            models.SuscripcionPush.ultimo_exito_en,
        ).order_by(models.SuscripcionPush.id)
    )
    assert filas.all() == [
        (sana.id, 0, reloj.ahora),  # entregada: se reinicia el conteo de fallos
        (fallando.id, 1, None),  # la caducada (410) y la de 10 fallos se borraron
    ]
