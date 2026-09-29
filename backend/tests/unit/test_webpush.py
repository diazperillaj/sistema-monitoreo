"""Canal Web Push (§10.2–§10.4): servicios permitidos, claves VAPID, cabeceras y errores."""

from typing import Any

import pytest
import requests
from pywebpush import WebPushException

from app.services import avisos, webpush
from app.services.webpush import (
    CanalWebPush,
    Destino,
    cargar_vapid,
    es_servicio_push,
    generar_claves,
    topic,
)


@pytest.mark.parametrize(
    ("endpoint", "valido"),
    [
        ("https://fcm.googleapis.com/fcm/send/abc:APA91", True),
        ("https://updates.push.services.mozilla.com/wpush/v2/gAAA", True),
        ("https://web.push.apple.com/QGuQyavXutnMH", True),
        ("https://wns2-bl2p.notify.windows.com/w/?token=x", True),
        ("http://fcm.googleapis.com/fcm/send/abc", False),  # sin cifrar
        ("https://fcm.googleapis.com.atacante.com/x", False),
        ("https://atacantefcm.googleapis.com/x", False),
        ("https://127.0.0.1/interno", False),
        ("https://alarma-db:5432/", False),
        ("no es una url", False),
    ],
)
def test_solo_servicios_de_push_de_los_navegadores(endpoint: str, valido: bool) -> None:
    assert es_servicio_push(endpoint) is valido


def test_topic_valido_para_el_servicio_de_push() -> None:
    assert topic("a-1-2-SIN_MOVIMIENTO") == "a-1-2-SIN_MOVIMIENTO"
    assert topic("a b/ñ") == "a_b__"
    assert len(topic("x" * 50)) == 32


def test_claves_vapid() -> None:
    publica, privada = generar_claves()
    assert len(publica) == 87 and publica.startswith("B")  # punto sin comprimir (65 bytes)
    assert len(privada) == 43  # 32 bytes en base64url sin relleno
    assert cargar_vapid(publica, privada) is not None
    otra_publica, _ = generar_claves()
    assert cargar_vapid(otra_publica, privada) is None  # no corresponden
    assert cargar_vapid(publica, "no-es-una-clave") is None
    assert cargar_vapid("", privada) is None


# ------------------------------------------------------------------ envío (sin red)
class RespuestaFalsa:
    def __init__(self, codigo: int) -> None:
        self.status_code = codigo
        self.headers: dict[str, str] = {}
        self.text = ""


class ServicioFalso:
    """Reemplaza a pywebpush.webpush: responde en orden lo que se le indique."""

    def __init__(self, *respuestas: int | type[Exception]) -> None:
        self.respuestas = list(respuestas)
        self.llamadas: list[dict[str, Any]] = []

    def __call__(self, **argumentos: Any) -> None:
        self.llamadas.append(argumentos)
        respuesta = self.respuestas.pop(0) if self.respuestas else 201
        if isinstance(respuesta, type):
            raise respuesta("sin red")
        if respuesta > 202:
            raise WebPushException("falló", response=RespuestaFalsa(respuesta))


@pytest.fixture
def canal() -> CanalWebPush:
    publica, privada = generar_claves()
    return CanalWebPush(cargar_vapid(publica, privada), "mailto:prueba@ejemplo.com", esperas=(0, 0))


DESTINO = Destino(7, "https://fcm.googleapis.com/fcm/send/abc", "p" * 87, "a" * 22)
ALARMA = avisos.Aviso("🚨 Baño", "texto", "a-1-2-SIN_MOVIMIENTO", "/casa/1", "alarma", True, 1)


async def enviar(
    canal: CanalWebPush, monkeypatch: pytest.MonkeyPatch, *respuestas: int | type[Exception]
) -> tuple[str, ServicioFalso]:
    servicio = ServicioFalso(*respuestas)
    monkeypatch.setattr(webpush, "webpush", servicio)
    [resultado] = await canal.enviar([DESTINO], ALARMA)
    assert resultado.suscripcion_id == DESTINO.id
    return resultado.entrega, servicio


async def test_envio_con_urgencia_ttl_y_topic(
    canal: CanalWebPush, monkeypatch: pytest.MonkeyPatch
) -> None:
    entrega, servicio = await enviar(canal, monkeypatch, 201)
    assert entrega == "entregado"
    [llamada] = servicio.llamadas
    assert llamada["ttl"] == 600
    assert llamada["headers"] == {"Urgency": "high", "Topic": "a-1-2-SIN_MOVIMIENTO"}
    assert llamada["vapid_claims"] == {"sub": "mailto:prueba@ejemplo.com"}
    assert '"titulo": "🚨 Baño"' in llamada["data"]

    normal = avisos.Aviso("✅ Central en línea", "Casa", "c-1", "/casa/1", "central", False, 1)
    await canal.enviar([DESTINO], normal)
    assert servicio.llamadas[1]["ttl"] == 3600
    assert servicio.llamadas[1]["headers"]["Urgency"] == "normal"
    # webpush() agrega aud y exp al diccionario: cada envío debe recibir uno nuevo
    assert servicio.llamadas[1]["vapid_claims"] is not llamada["vapid_claims"]


@pytest.mark.parametrize(
    ("respuestas", "entrega", "intentos"),
    [
        ((410,), "caducada", 1),
        ((404,), "caducada", 1),
        ((413,), "rechazado", 1),  # más de 4 KB: reintentar no lo arregla
        ((403,), "rechazado", 1),
        ((500, 503, 201), "entregado", 3),
        ((429, 201), "entregado", 2),
        ((500, 500, 500), "fallo", 3),  # el primero y 2 reintentos
        ((requests.ConnectionError, requests.Timeout, 201), "entregado", 3),
        ((requests.ConnectionError,) * 3, "fallo", 3),
    ],
)
async def test_errores_de_envio(
    canal: CanalWebPush,
    monkeypatch: pytest.MonkeyPatch,
    respuestas: tuple,
    entrega: str,
    intentos: int,
) -> None:
    obtenida, servicio = await enviar(canal, monkeypatch, *respuestas)
    assert obtenida == entrega
    assert len(servicio.llamadas) == intentos


async def test_sin_claves_no_se_envia_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    servicio = ServicioFalso()
    monkeypatch.setattr(webpush, "webpush", servicio)
    inactivo = CanalWebPush(None, "mailto:prueba@ejemplo.com")
    assert not inactivo.activo
    assert await inactivo.enviar([DESTINO], ALARMA) == []
    assert servicio.llamadas == []
