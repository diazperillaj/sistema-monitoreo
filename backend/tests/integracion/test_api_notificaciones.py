"""Web Push por la API (§8.7): clave pública, suscripciones, preferencias y prueba."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.main import create_app
from app.services.webpush import generar_claves
from tests.ayudas import CanalFalso, CrearCliente, Datos, Entrar, ajustes
from tests.conftest import cliente_para

FCM = "https://fcm.googleapis.com/fcm/send/dispositivo-de-ana"
CLAVES = {"p256dh": "B" + "p" * 86, "auth": "a" * 22}


@pytest.fixture
def canal(app: FastAPI) -> CanalFalso:
    falso = CanalFalso()
    app.state.notificador.webpush = falso
    return falso


@pytest.fixture
async def ana(api: httpx.AsyncClient, datos: Datos, entrar: Entrar) -> httpx.AsyncClient:
    await datos.usuario("ana@ejemplo.com", nombre="Ana")
    await entrar(api, "ana@ejemplo.com")
    return api


async def suscripciones(db: AsyncSession) -> list[tuple[str, int]]:
    filas = await db.execute(
        select(models.SuscripcionPush.endpoint, models.SuscripcionPush.usuario_id).order_by(
            models.SuscripcionPush.id
        )
    )
    return [(endpoint, usuario_id) for endpoint, usuario_id in filas.all()]


# ------------------------------------------------------------------ clave pública
async def test_sin_claves_vapid_la_clave_publica_responde_503(api: httpx.AsyncClient) -> None:
    r = await api.get("/api/v1/push/clave-publica")
    assert (r.status_code, r.json()["detail"]["codigo"]) == (503, "webpush_no_disponible")


async def test_con_claves_vapid_entrega_la_publica(url_db: str) -> None:
    publica, privada = generar_claves()
    app = create_app(
        ajustes(
            database_url=url_db,
            vapid_clave_publica=publica,
            vapid_clave_privada=privada,
            vapid_sujeto="mailto:prueba@ejemplo.com",
        )
    )
    try:
        async with cliente_para(app) as cliente:
            r = await cliente.get("/api/v1/push/clave-publica")  # pública: sin sesión
        assert (r.status_code, r.json()) == (200, {"clave": publica})
    finally:
        await app.state.motor.dispose()


# ------------------------------------------------------------------ suscripciones
async def test_suscribir_y_dar_de_baja(
    ana: httpx.AsyncClient, db: AsyncSession, datos: Datos
) -> None:
    r = await ana.post("/api/v1/push/suscripciones", json={"endpoint": FCM, "keys": CLAVES})
    assert r.status_code == 201
    [(endpoint, _)] = await suscripciones(db)
    assert endpoint == FCM

    # Otra persona no puede borrarla
    beto = await datos.usuario("beto@ejemplo.com")
    ajena = await datos.suscripcion(beto)
    r = await ana.request("DELETE", "/api/v1/push/suscripciones", json={"endpoint": ajena.endpoint})
    assert r.status_code == 204
    assert len(await suscripciones(db)) == 2

    r = await ana.request("DELETE", "/api/v1/push/suscripciones", json={"endpoint": FCM})
    assert r.status_code == 204
    assert [e for e, _ in await suscripciones(db)] == [ajena.endpoint]


async def test_el_dispositivo_pasa_a_quien_inicia_sesion(
    ana: httpx.AsyncClient,
    nuevo_cliente: CrearCliente,
    datos: Datos,
    entrar: Entrar,
    db: AsyncSession,
) -> None:
    await ana.post("/api/v1/push/suscripciones", json={"endpoint": FCM, "keys": CLAVES})
    beto_usuario = await datos.usuario("beto@ejemplo.com")
    beto = nuevo_cliente()
    await entrar(beto, "beto@ejemplo.com")
    r = await beto.post("/api/v1/push/suscripciones", json={"endpoint": FCM, "keys": CLAVES})
    assert r.status_code == 201
    assert await suscripciones(db) == [(FCM, beto_usuario.id)]  # una sola fila, ahora de Beto


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"endpoint": "http://fcm.googleapis.com/fcm/send/x", "keys": CLAVES},
        {"endpoint": "https://api.atacante.com/robar", "keys": CLAVES},
        {"endpoint": "https://127.0.0.1:8011/api/v1/casas", "keys": CLAVES},
        {"endpoint": FCM, "keys": {"p256dh": "corta", "auth": CLAVES["auth"]}},
        {"endpoint": FCM, "keys": {"p256dh": CLAVES["p256dh"], "auth": "no base64!" * 3}},
        {"endpoint": FCM},
    ],
)
async def test_suscripciones_invalidas_responden_400(
    ana: httpx.AsyncClient, db: AsyncSession, cuerpo: dict
) -> None:
    r = await ana.post("/api/v1/push/suscripciones", json=cuerpo)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (400, "solicitud_invalida")
    assert await suscripciones(db) == []


async def test_sin_sesion_no_se_puede_suscribir(api: httpx.AsyncClient) -> None:
    r = await api.post("/api/v1/push/suscripciones", json={"endpoint": FCM, "keys": CLAVES})
    assert r.status_code == 401


# ------------------------------------------------------------------ preferencias
async def test_preferencias(ana: httpx.AsyncClient) -> None:
    await ana.post("/api/v1/push/suscripciones", json={"endpoint": FCM, "keys": CLAVES})
    r = await ana.get("/api/v1/notificaciones/preferencias")
    assert r.json() == {
        "webpush": {"activo": True, "dispositivos": 1},
        "telegram": {
            "disponible": False,
            "bot": None,
            "vinculado": False,
            "cuenta": None,
            "vinculado_en": None,
            "activo": False,
        },
    }
    r = await ana.patch("/api/v1/notificaciones/preferencias", json={"webpush": False})
    assert r.json()["webpush"] == {"activo": False, "dispositivos": 1}  # pausa sin borrar

    r = await ana.patch("/api/v1/notificaciones/preferencias", json={"telegram": True})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "telegram_no_vinculado")


# ------------------------------------------------------------------ prueba
async def test_notificacion_de_prueba_a_mis_dispositivos(
    app: FastAPI, ana: httpx.AsyncClient, canal: CanalFalso, datos: Datos
) -> None:
    otra = "https://updates.push.services.mozilla.com/wpush/v2/firefox-de-ana"
    await ana.post("/api/v1/push/suscripciones", json={"endpoint": FCM, "keys": CLAVES})
    await ana.post("/api/v1/push/suscripciones", json={"endpoint": otra, "keys": CLAVES})
    await datos.suscripcion(await datos.usuario("beto@ejemplo.com"))  # de otra persona

    r = await ana.post("/api/v1/notificaciones/prueba", json={"canal": "webpush"})
    assert (r.status_code, r.json()) == (202, {"webpush": 2, "telegram": False})
    await app.state.notificador.esperar()
    [(aviso, destinos)] = canal.envios
    assert aviso.titulo == "🔔 Notificación de prueba"
    assert sorted(d.endpoint for d in destinos) == sorted([FCM, otra])


async def test_prueba_sin_dispositivos_ni_telegram(
    app: FastAPI, ana: httpx.AsyncClient, canal: CanalFalso
) -> None:
    r = await ana.post("/api/v1/notificaciones/prueba", json={"canal": "todos"})
    assert r.json() == {"webpush": 0, "telegram": False}
    await app.state.notificador.esperar()
    assert canal.envios == []
    r = await ana.post("/api/v1/notificaciones/prueba", json={"canal": "telegram"})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "telegram_no_disponible")


async def test_prueba_sin_claves_vapid_responde_503(ana: httpx.AsyncClient) -> None:
    r = await ana.post("/api/v1/notificaciones/prueba", json={"canal": "webpush"})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (503, "webpush_no_disponible")
