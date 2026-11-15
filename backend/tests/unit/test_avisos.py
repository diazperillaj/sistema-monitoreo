"""Textos y tags de las notificaciones (§10.1)."""

from datetime import UTC, datetime, timedelta

from app import models
from app.services import avisos

INICIO = datetime(2026, 9, 27, 19, 5, 10, tzinfo=UTC)  # 14:05 en Bogotá


def alarma(tipo: str = "SIN_MOVIMIENTO", nodo_id: int | None = 2, **campos) -> models.Alarma:
    valores = {"id": 12, "casa_id": 1, "inicio_en": INICIO, "limite_s": 600, "valor": None}
    return models.Alarma(tipo=tipo, nodo_id=nodo_id, **(valores | campos))


def test_alarma_abierta() -> None:
    aviso = avisos.alarma_abierta(alarma(), "Casa de la abuela")
    assert aviso.payload() == {
        "titulo": "🚨 Baño",
        "cuerpo": "Sin movimiento por 10 min · Casa de la abuela",
        "tag": "a-1-2-SIN_MOVIMIENTO",
        "url": "/casa/1",
        "tipo": "alarma",
        "casa_id": 1,
        "alarma_id": 12,
        "nodo_id": 2,
    }
    assert aviso.urgente  # Urgency high y TTL corto; no va en el payload


def test_temperatura_y_gas_del_nodo_4() -> None:
    gas = avisos.alarma_abierta(alarma("GAS", 4, limite_s=240), "Casa")
    temperatura = avisos.alarma_abierta(
        alarma("TEMPERATURA", 4, limite_s=None, valor=61.26), "Casa"
    )
    assert (gas.titulo, gas.cuerpo) == ("🚨 Cocina · gas", "Gas detectado por más de 4 min · Casa")
    assert temperatura.cuerpo == "Temperatura alta: 61.3 °C · Casa"
    assert gas.tag != temperatura.tag  # cada alarma se reemplaza por separado


def test_alarma_resuelta() -> None:
    assert avisos.alarma_resuelta(alarma(), "Laura", "silenciar").cuerpo == "Laura la silenció"
    assert avisos.alarma_resuelta(alarma(), "Laura", "desactivar").cuerpo == "Laura la desactivó"
    resuelta = avisos.alarma_resuelta(alarma(), None, None)
    assert (resuelta.titulo, resuelta.cuerpo, resuelta.tag) == (
        "🔕 Baño",
        "Se normalizó",
        "a-1-2-SIN_MOVIMIENTO",  # reemplaza a la notificación de la alarma
    )
    assert resuelta.alarma_id is None  # no cuenta como aviso de la alarma


def test_conexion_de_nodo_y_central() -> None:
    nodo = avisos.nodo_sin_conexion(alarma("NODO_SIN_CONEXION", 3), "Casa")
    assert (nodo.titulo, nodo.cuerpo, nodo.tag, nodo.urgente) == (
        "⚠️ Cocina · agua sin conexión",
        "Casa",
        "n-1-3",
        False,
    )
    caida = avisos.central_desconectada(alarma("CENTRAL_DESCONECTADA", None), "Casa")
    assert (caida.titulo, caida.cuerpo, caida.tag) == (
        "📡 Central desconectada",
        "Sin datos desde las 14:05 · Casa",
        "c-1",
    )
    volvio = avisos.central_en_linea(1, "Casa")
    assert (volvio.titulo, volvio.tag, volvio.alarma_id) == ("✅ Central en línea", "c-1", None)


def test_recordatorios() -> None:
    ahora = INICIO + timedelta(minutes=10, seconds=40)
    sensor = avisos.recordatorio(alarma(), "Casa", ahora)
    assert (sensor.titulo, sensor.cuerpo, sensor.tipo, sensor.urgente) == (
        "⏰ Sigue activa: Baño",
        "Sin movimiento por 10 min · hace 10 min",
        "recordatorio",
        True,
    )
    nodo = avisos.recordatorio(alarma("NODO_SIN_CONEXION", 3), "Casa", ahora)
    assert (nodo.titulo, nodo.cuerpo, nodo.urgente) == (
        "⏰ Sigue sin conexión: Cocina · agua",
        "Desde las 14:05 · Casa",
        False,
    )
    central = avisos.recordatorio(alarma("CENTRAL_DESCONECTADA", None), "Casa", ahora)
    assert (central.titulo, central.tag) == ("⏰ Central sigue desconectada", "c-1")
    assert sensor.tag == avisos.alarma_abierta(alarma(), "Casa").tag  # la reemplaza


def test_prueba() -> None:
    prueba = avisos.prueba()
    assert (prueba.titulo, prueba.casa_id, prueba.url) == ("🔔 Notificación de prueba", None, "/")
