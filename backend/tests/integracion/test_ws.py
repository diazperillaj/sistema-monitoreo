"""WebSocket de una casa (§9): quién puede abrirlo y qué recibe."""

import contextlib
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx_ws import AsyncWebSocketSession, WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from app import models
from app.api.ws import NO_AUTENTICADO, SIN_PERMISO
from tests.ayudas import ORIGEN, Datos, Entrar, en_bytes, payload

EsperaWs = contextlib.AbstractAsyncContextManager[AsyncWebSocketSession]


@contextlib.asynccontextmanager
async def abrir_navegador(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Un cliente que habla HTTP y WebSocket con la app, como la PWA desde ORIGEN.

    No es un fixture: el transporte abre un grupo de tareas de anyio, que debe cerrarse en
    la misma tarea en que se abrió, y pytest-asyncio arma y desarma los fixtures en tareas
    distintas."""
    transporte = ASGIWebSocketTransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url=ORIGEN, headers={"Origin": ORIGEN}
    ) as cliente:
        yield cliente


def conectar(cliente: httpx.AsyncClient, casa_id: int, **cabeceras: str) -> EsperaWs:
    return aconnect_ws(
        f"/ws/v1/casas/{casa_id}",
        cliente,
        keepalive_ping_interval_seconds=None,
        headers=dict(cabeceras),
    )


async def recibir_hasta(ws: AsyncWebSocketSession, tipo: str) -> list[dict[str, Any]]:
    """Los mensajes recibidos hasta el primero de `tipo`, incluido."""
    mensajes: list[dict[str, Any]] = []
    while not mensajes or mensajes[-1]["tipo"] != tipo:
        mensajes.append(await ws.receive_json(timeout=5))
    return mensajes


async def codigo_de_cierre(ws: AsyncWebSocketSession) -> int:
    with pytest.raises(WebSocketDisconnect) as cierre:
        await ws.receive_json(timeout=5)
    return cierre.value.code


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    await datos.usuario("carla@ejemplo.com", nombre="Carla")  # no es miembro
    casa = await datos.casa("casa-dev", "Casa de prueba")
    await datos.miembro(ana, casa, "cuidador")
    return casa


async def test_sin_sesion_cierra_con_4401(app: FastAPI, casa: models.Casa) -> None:
    async with abrir_navegador(app) as navegador, conectar(navegador, casa.id) as ws:
        assert await codigo_de_cierre(ws) == NO_AUTENTICADO


async def test_otro_origen_cierra_con_4403(app: FastAPI, casa: models.Casa, entrar: Entrar) -> None:
    async with abrir_navegador(app) as navegador:
        await entrar(navegador, "ana@ejemplo.com")
        async with conectar(navegador, casa.id, Origin="https://sitio-malicioso.test") as ws:
            assert await codigo_de_cierre(ws) == SIN_PERMISO


async def test_quien_no_es_miembro_recibe_4403(
    app: FastAPI, casa: models.Casa, entrar: Entrar
) -> None:
    async with abrir_navegador(app) as navegador:
        await entrar(navegador, "carla@ejemplo.com")
        async with conectar(navegador, casa.id) as ws:
            assert await codigo_de_cierre(ws) == SIN_PERMISO
        async with conectar(navegador, casa.id + 1000) as ws:  # ni siquiera existe
            assert await codigo_de_cierre(ws) == SIN_PERMISO


async def test_el_miembro_recibe_el_estado_y_responde_al_ping(
    app: FastAPI, casa: models.Casa, entrar: Entrar
) -> None:
    async with abrir_navegador(app) as navegador:
        await entrar(navegador, "ana@ejemplo.com")
        async with conectar(navegador, casa.id) as ws:
            inicial = await ws.receive_json(timeout=5)
            assert inicial == {
                "tipo": "estado",
                "data": {
                    "casa_id": casa.id,
                    "online": False,
                    "online_cambio_en": None,
                    "recibido_en": None,
                    "antiguedad_s": None,
                    "central": None,
                    "alarmas_abiertas": [],
                },
            }
            await ws.send_json({"tipo": "ping"})
            assert await ws.receive_json(timeout=5) == {"tipo": "pong"}


async def test_el_estado_y_las_alarmas_llegan_en_vivo(
    app: FastAPI, casa: models.Casa, entrar: Entrar
) -> None:
    async with abrir_navegador(app) as navegador:
        await entrar(navegador, "ana@ejemplo.com")
        async with conectar(navegador, casa.id) as ws:
            await ws.receive_json(timeout=5)  # estado inicial
            await app.state.procesador.recibir_estado(
                "casa-dev", en_bytes(payload("estado_alarma"))
            )

            mensajes = await recibir_hasta(ws, "estado")
            assert [m["tipo"] for m in mensajes] == [
                "central",
                "alarma",
                "evento",
                "evento",
                "estado",
            ]
            central, alarma, conectada, abierta, estado = mensajes
            assert central["online"] is True
            assert alarma["evento"] == "abre"
            assert alarma["data"]["nodo_nombre"] == "Baño"
            assert alarma["data"]["texto"] == "Sin movimiento por 10 min"
            assert conectada["data"]["texto"] == "La central se conectó"
            assert abierta["data"]["texto"] == "Baño: Sin movimiento por 10 min"
            datos = estado["data"]
            assert datos["online"] is True
            assert datos["antiguedad_s"] == 0
            assert [a["id"] for a in datos["alarmas_abiertas"]] == [alarma["data"]["id"]]
            # El payload de la central con sus mismos nombres de campo (§4.3)
            assert datos["central"]["horaValida"] is True
            assert datos["central"]["nodos"][2]["enLinea"] is True
            assert datos["central"]["nodos"][2]["al"] == 1


async def test_otra_casa_no_recibe_nada(
    app: FastAPI, datos: Datos, casa: models.Casa, entrar: Entrar
) -> None:
    async with abrir_navegador(app) as navegador:
        otra = await datos.casa("casa-otra")
        await entrar(navegador, "ana@ejemplo.com")
        async with conectar(navegador, casa.id) as ws:
            await ws.receive_json(timeout=5)
            await app.state.procesador.recibir_estado(
                otra.codigo, en_bytes(payload("estado_alarma"))
            )
            await ws.send_json({"tipo": "ping"})
            assert await ws.receive_json(timeout=5) == {"tipo": "pong"}  # lo único que llega


async def test_cerrar_la_sesion_corta_el_websocket_en_el_siguiente_ping(
    app: FastAPI, casa: models.Casa, entrar: Entrar
) -> None:
    async with abrir_navegador(app) as navegador:
        await entrar(navegador, "ana@ejemplo.com")
        async with conectar(navegador, casa.id) as ws:
            await ws.receive_json(timeout=5)
            assert app.state.hub.hay_clientes(casa.id)
            assert (await navegador.post("/api/v1/auth/logout")).status_code == 204
            await ws.send_json({"tipo": "ping"})
            assert await codigo_de_cierre(ws) == NO_AUTENTICADO
        assert not app.state.hub.hay_clientes(casa.id)


async def test_una_peticion_http_a_la_ruta_del_websocket_da_404(
    app: FastAPI, casa: models.Casa
) -> None:
    async with abrir_navegador(app) as navegador:
        respuesta = await navegador.get(f"/ws/v1/casas/{casa.id}")
        assert respuesta.status_code == 404
        assert respuesta.json()["detail"]["codigo"] == "no_encontrado"
