"""Comandos por la API (§6.5, §8.4): publicación, confirmación, vencimiento y rechazos."""

from typing import Any
from unittest.mock import ANY

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from tests.ayudas import Datos, Entrar, MqttFalso, en_bytes, payload

CASA = "casa-dev"


@pytest.fixture
def mqtt(app: FastAPI) -> MqttFalso:
    falso = MqttFalso()
    app.state.mqtt = falso
    return falso


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    beto = await datos.usuario("beto@ejemplo.com", nombre="Beto")
    casa = await datos.casa(CASA, "Casa de prueba")
    await datos.miembro(ana, casa, "admin")
    await datos.miembro(beto, casa, "cuidador")
    return casa


async def central(
    app: FastAPI, fixture: str = "estado_normal", *, retenido: bool = False, **cambios: Any
) -> None:
    """La central publica un estado (en vivo, salvo que se diga lo contrario)."""
    await app.state.procesador.recibir_estado(CASA, en_bytes(payload(fixture, **cambios)), retenido)


@pytest.fixture
async def ana(
    app: FastAPI, api: httpx.AsyncClient, casa: models.Casa, entrar: Entrar, mqtt: MqttFalso
) -> httpx.AsyncClient:
    """Ana con la sesión abierta, y la central conectada con todos sus nodos en línea."""
    await central(app)
    await entrar(api, "ana@ejemplo.com")
    return api


def ruta(casa: models.Casa, resto: str = "") -> str:
    return f"/api/v1/casas/{casa.id}/comandos{resto}"


async def ver(cliente: httpx.AsyncClient, casa: models.Casa, comando_id: int) -> dict[str, Any]:
    r = await cliente.get(ruta(casa, f"/{comando_id}"))
    assert r.status_code == 200, r.text
    return r.json()


async def ultimo_evento(db: AsyncSession) -> models.Evento:
    consulta = select(models.Evento).order_by(models.Evento.id.desc()).limit(1)
    evento = await db.scalar(consulta.execution_options(populate_existing=True))
    assert evento is not None
    return evento


async def cantidad_de_comandos(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(models.Comando)) or 0


# ------------------------------------------------------------------ enviar
async def test_enviar_publica_y_queda_pendiente(
    ana: httpx.AsyncClient, casa: models.Casa, mqtt: MqttFalso, db: AsyncSession
) -> None:
    r = await ana.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})
    assert r.status_code == 202, r.text
    usuario_id = r.json()["usuario"]["id"]
    assert r.json() == {
        "id": ANY,
        "nodo_id": 2,
        "accion": "silenciar",
        "sub": 0,
        "estado": "pendiente",
        "creado_en": ANY,
        "resuelto_en": None,
        "usuario": {"id": usuario_id, "nombre": "Ana"},
    }
    assert mqtt.publicados == [("casa/casa-dev/cmd", "2:silenciar:0")]
    evento = await ultimo_evento(db)
    assert (evento.texto, evento.origen, evento.tipo, evento.usuario_id, evento.nodo_id) == (
        "Ana silenció Baño",
        "usuario",
        "comando",
        usuario_id,
        2,
    )


async def test_el_cuidador_tambien_puede_enviar(
    app: FastAPI,
    api: httpx.AsyncClient,
    casa: models.Casa,
    entrar: Entrar,
    mqtt: MqttFalso,
) -> None:
    await central(app)
    await entrar(api, "beto@ejemplo.com")
    r = await api.post(ruta(casa), json={"nodo": 4, "accion": "desactivar", "sub": 1})
    assert r.status_code == 202
    assert mqtt.publicados == [("casa/casa-dev/cmd", "4:desactivar:1")]


# ------------------------------------------------------------------ confirmar
@pytest.mark.parametrize(
    ("cuerpo", "antes", "despues"),
    [
        ({"nodo": 2, "accion": "desactivar"}, {}, {"n2": {"hab": 0}}),
        ({"nodo": 2, "accion": "activar"}, {"n2": {"hab": 0}}, {}),
        ({"nodo": 4, "accion": "activar", "sub": 1}, {"n4": {"hab": 1}}, {}),
        ({"nodo": 0, "accion": "desactivar"}, {}, {"n0": {"hab": 0}}),
    ],
)
async def test_un_estado_posterior_confirma_el_comando(
    app: FastAPI,
    ana: httpx.AsyncClient,
    casa: models.Casa,
    cuerpo: dict,
    antes: dict,
    despues: dict,
) -> None:
    await central(app, **antes)
    comando = (await ana.post(ruta(casa), json=cuerpo)).json()
    await central(app, **antes)  # un estado que aún no refleja el cambio
    assert (await ver(ana, casa, comando["id"]))["estado"] == "pendiente"

    await central(app, **despues)
    confirmado = await ver(ana, casa, comando["id"])
    assert confirmado["estado"] == "confirmado"
    assert confirmado["resuelto_en"] is not None


async def test_silenciar_confirma_y_cierra_la_alarma_a_nombre_del_usuario(
    app: FastAPI, ana: httpx.AsyncClient, casa: models.Casa, db: AsyncSession
) -> None:
    await central(app, "estado_alarma")  # Baño sin movimiento
    comando = (await ana.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})).json()
    await central(app, "estado_alarma", n2={"al": 0})

    assert (await ver(ana, casa, comando["id"]))["estado"] == "confirmado"
    alarma = await db.scalar(select(models.Alarma).execution_options(populate_existing=True))
    assert alarma is not None
    assert (alarma.cerrada_por, alarma.cerrada_por_usuario_id) == (
        "usuario",
        comando["usuario"]["id"],
    )
    assert (await ultimo_evento(db)).texto == (
        "Baño: Sin movimiento por 10 min · silenciada por Ana"
    )


async def test_silenciar_todo(
    app: FastAPI, ana: httpx.AsyncClient, casa: models.Casa, mqtt: MqttFalso
) -> None:
    await central(app, n2={"al": 1}, n4={"al": 4})
    r = await ana.post(ruta(casa, "/silenciar-todo"))
    assert r.status_code == 202, r.text
    comando = r.json()
    assert (comando["nodo_id"], comando["accion"], comando["sub"]) == (None, "silenciar", 0)
    assert mqtt.publicados == [("casa/casa-dev/cmd", "todo:silenciar")]

    await central(app, n4={"al": 4})  # el gas sigue sonando
    assert (await ver(ana, casa, comando["id"]))["estado"] == "pendiente"
    await central(app)
    assert (await ver(ana, casa, comando["id"]))["estado"] == "confirmado"


async def test_un_estado_retenido_no_confirma(
    app: FastAPI, ana: httpx.AsyncClient, casa: models.Casa
) -> None:
    comando = (await ana.post(ruta(casa), json={"nodo": 2, "accion": "desactivar"})).json()
    await central(app, retenido=True, n2={"hab": 0})
    assert (await ver(ana, casa, comando["id"]))["estado"] == "pendiente"


# ------------------------------------------------------------------ vencer
async def test_sin_estado_que_lo_confirme_queda_sin_confirmar(
    app: FastAPI, ana: httpx.AsyncClient, casa: models.Casa, db: AsyncSession
) -> None:
    comando = (await ana.post(ruta(casa), json={"nodo": 2, "accion": "desactivar"})).json()
    await app.state.procesador.vencer_comandos(0)

    vencido = await ver(ana, casa, comando["id"])
    assert vencido["estado"] == "sin_confirmar"
    assert vencido["resuelto_en"] is not None
    evento = await ultimo_evento(db)
    assert evento.texto == "La central no confirmó el comando de Ana: desactivar Baño"
    assert (evento.origen, evento.tipo) == ("backend", "comando")

    await central(app, n2={"hab": 0})  # llega tarde: ya no cambia nada
    assert (await ver(ana, casa, comando["id"]))["estado"] == "sin_confirmar"


async def test_si_no_se_pudo_publicar_vence_como_cualquier_otro(
    app: FastAPI, ana: httpx.AsyncClient, casa: models.Casa, mqtt: MqttFalso
) -> None:
    mqtt.falla = True
    r = await ana.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})
    assert r.status_code == 202
    await app.state.procesador.vencer_comandos(0)
    assert (await ver(ana, casa, r.json()["id"]))["estado"] == "sin_confirmar"


# ------------------------------------------------------------------ rechazos
async def test_con_la_central_desconectada_responde_409(
    app: FastAPI, ana: httpx.AsyncClient, casa: models.Casa, mqtt: MqttFalso, db: AsyncSession
) -> None:
    await app.state.procesador.recibir_online(CASA, b"0")
    for r in (
        await ana.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"}),
        await ana.post(ruta(casa, "/silenciar-todo")),
    ):
        assert r.status_code == 409
        assert r.json()["detail"] == {
            "codigo": "central_desconectada",
            "mensaje": "La central está desconectada.",
        }
    assert mqtt.publicados == []
    assert await cantidad_de_comandos(db) == 0


async def test_una_casa_sin_datos_de_su_central_responde_409(
    api: httpx.AsyncClient, casa: models.Casa, entrar: Entrar, mqtt: MqttFalso
) -> None:
    await entrar(api, "ana@ejemplo.com")
    r = await api.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "central_desconectada")


async def test_con_el_nodo_sin_conexion_responde_409(
    app: FastAPI, ana: httpx.AsyncClient, casa: models.Casa, mqtt: MqttFalso
) -> None:
    await central(app, n3={"enLinea": False, "hace": 25})
    r = await ana.post(ruta(casa), json={"nodo": 3, "accion": "desactivar"})
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "nodo_sin_conexion"
    assert r.json()["detail"]["mensaje"] == "El nodo no tiene conexión."
    # Los demás nodos, y silenciar todo, siguen funcionando
    assert (await ana.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})).status_code == 202
    assert (await ana.post(ruta(casa, "/silenciar-todo"))).status_code == 202
    assert [carga for _, carga in mqtt.publicados] == ["2:silenciar:0", "todo:silenciar"]


async def test_sin_conexion_con_el_broker_responde_503(
    ana: httpx.AsyncClient, casa: models.Casa, mqtt: MqttFalso, db: AsyncSession
) -> None:
    mqtt.conectado = False
    r = await ana.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (503, "mqtt_no_disponible")
    assert await cantidad_de_comandos(db) == 0


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"nodo": 2, "accion": "activar", "sub": 1},  # la presencia es solo del nodo 4
        {"nodo": 4, "accion": "silenciar", "sub": 1},
        {"nodo": 5, "accion": "silenciar"},
        {"nodo": 2, "accion": "apagar"},
        {"nodo": "2:silenciar:0", "accion": "silenciar"},
        {"accion": "silenciar"},
    ],
)
async def test_datos_invalidos_responden_400(
    ana: httpx.AsyncClient, casa: models.Casa, mqtt: MqttFalso, cuerpo: dict
) -> None:
    r = await ana.post(ruta(casa), json=cuerpo)
    assert r.status_code == 400
    assert r.json()["detail"]["codigo"] == "solicitud_invalida"
    assert mqtt.publicados == []


async def test_limite_de_30_comandos_por_minuto_y_usuario(
    ana: httpx.AsyncClient,
    nuevo_cliente: Any,
    casa: models.Casa,
    entrar: Entrar,
) -> None:
    for _ in range(30):
        r = await ana.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})
        assert r.status_code == 202
    r = await ana.post(ruta(casa, "/silenciar-todo"))
    assert r.status_code == 429
    assert r.json()["detail"]["codigo"] == "demasiados_intentos"
    assert int(r.headers["Retry-After"]) >= 1

    beto = nuevo_cliente()  # el límite es por usuario
    await entrar(beto, "beto@ejemplo.com")
    assert (await beto.post(ruta(casa), json={"nodo": 2, "accion": "silenciar"})).status_code == 202


# ------------------------------------------------------------------ consultar
async def test_ultimos_comandos_y_uno_por_id(
    ana: httpx.AsyncClient, casa: models.Casa, datos: Datos, db: AsyncSession
) -> None:
    ids = []
    for cuerpo in (
        {"nodo": 2, "accion": "silenciar"},
        {"nodo": 1, "accion": "desactivar"},
        {"nodo": 4, "accion": "activar", "sub": 1},
    ):
        ids.append((await ana.post(ruta(casa), json=cuerpo)).json()["id"])

    ultimos = (await ana.get(ruta(casa), params={"limit": 2})).json()
    assert [c["id"] for c in ultimos] == [ids[2], ids[1]]
    assert (await ver(ana, casa, ids[0]))["accion"] == "silenciar"

    otra = await datos.casa("casa-otra")
    db.add(
        models.Comando(
            casa_id=otra.id,
            nodo_id=2,
            accion="silenciar",
            sub=0,
            payload="2:silenciar:0",
            estado="pendiente",
        )
    )
    await db.commit()
    ajeno = await db.scalar(select(func.max(models.Comando.id)))
    assert (await ana.get(ruta(casa, f"/{ajeno}"))).status_code == 404  # es de otra casa
    assert (await ana.get(ruta(casa, "/999999"))).status_code == 404
