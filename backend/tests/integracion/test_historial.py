"""Estado en vivo, alarmas y eventos por REST (§8.3, §8.5): permisos, filtros y paginación."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from tests.ayudas import Datos, Entrar, en_bytes, payload

INICIO = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    casa = await datos.casa("casa-dev", "Casa de prueba")
    await datos.miembro(ana, casa, "cuidador")
    return casa


@pytest.fixture
async def dentro(api: httpx.AsyncClient, casa: models.Casa, entrar: Entrar) -> httpx.AsyncClient:
    await entrar(api, "ana@ejemplo.com")
    return api


# ------------------------------------------------------------------ estado
async def test_estado_sin_datos_de_la_central(dentro: httpx.AsyncClient, casa: models.Casa) -> None:
    r = await dentro.get(f"/api/v1/casas/{casa.id}/estado")
    assert r.status_code == 200
    assert r.json() == {
        "casa_id": casa.id,
        "online": False,
        "online_cambio_en": None,
        "recibido_en": None,
        "antiguedad_s": None,
        "central": None,
        "alarmas_abiertas": [],
    }


async def test_estado_con_la_central_en_linea(
    app: FastAPI, dentro: httpx.AsyncClient, casa: models.Casa
) -> None:
    await app.state.procesador.recibir_estado(casa.codigo, en_bytes(payload("estado_alarma")))
    r = await dentro.get(f"/api/v1/casas/{casa.id}/estado")
    assert r.status_code == 200
    estado = r.json()
    assert estado["online"] is True
    assert 0 <= estado["antiguedad_s"] <= 5
    assert estado["central"] == payload("estado_alarma")  # los mismos campos y valores (§4.3)
    [alarma] = estado["alarmas_abiertas"]
    assert alarma["nodo_nombre"] == "Baño"
    assert alarma["texto"] == "Sin movimiento por 10 min"
    assert alarma["fin_en"] is None


# ------------------------------------------------------------------ alarmas
async def alarmas_de_prueba(db: AsyncSession, casa: models.Casa, laura: models.Usuario) -> None:
    """5 alarmas, de la más antigua a la más reciente, una cada hora desde INICIO."""
    filas = [
        (2, "SIN_MOVIMIENTO", "usuario", laura.id),
        (4, "GAS", "central", None),
        (3, "NODO_SIN_CONEXION", "automatica", None),
        (None, "CENTRAL_DESCONECTADA", None, None),  # abierta
        (2, "SIN_MOVIMIENTO", None, None),  # abierta
    ]
    for hora, (nodo_id, tipo, cerrada_por, usuario_id) in enumerate(filas):
        inicio = INICIO + timedelta(hours=hora)
        db.add(
            models.Alarma(
                casa_id=casa.id,
                nodo_id=nodo_id,
                tipo=tipo,
                inicio_en=inicio,
                fin_en=inicio + timedelta(seconds=90) if cerrada_por else None,
                limite_s=240 if tipo == "GAS" else 600,
                cerrada_por=cerrada_por,
                cerrada_por_usuario_id=usuario_id,
            )
        )
    await db.commit()


async def test_alarmas_paginadas_de_la_mas_reciente_a_la_mas_antigua(
    dentro: httpx.AsyncClient, db: AsyncSession, datos: Datos, casa: models.Casa
) -> None:
    laura = await datos.usuario("laura@ejemplo.com", nombre="Laura")
    await alarmas_de_prueba(db, casa, laura)
    ruta = f"/api/v1/casas/{casa.id}/alarmas"

    ids: list[int] = []
    siguiente = None
    for _ in range(3):
        params = {"limit": 2} | ({"antes_de_id": siguiente} if siguiente else {})
        pagina = (await dentro.get(ruta, params=params)).json()
        ids += [alarma["id"] for alarma in pagina["items"]]
        siguiente = pagina["siguiente"]
    assert ids == [5, 4, 3, 2, 1]
    assert siguiente is None

    primera = (await dentro.get(ruta, params={"antes_de_id": 2})).json()["items"][0]
    assert primera["cerrada_por"] == "usuario"
    assert primera["cerrada_por_usuario"] == {"id": laura.id, "nombre": "Laura"}
    assert primera["duracion_s"] == 90
    assert primera["texto"] == "Sin movimiento por 10 min"
    central = (await dentro.get(ruta, params={"antes_de_id": 5, "limit": 1})).json()["items"][0]
    assert (central["nodo_id"], central["nodo_nombre"]) == (None, "Central")
    assert central["texto"] == "La central no está conectada"


@pytest.mark.parametrize(
    ("params", "esperados"),
    [
        ({"abiertas": "true"}, [5, 4]),
        ({"abiertas": "false"}, [3, 2, 1]),
        ({"nodo": 2}, [5, 1]),
        ({"tipo": "GAS"}, [2]),
        ({"desde": "2026-09-27T14:00:00Z"}, [5, 4, 3]),
        ({"hasta": "2026-09-27T09:00:00-05:00"}, [2, 1]),  # 14:00 UTC
        ({"desde": "2026-09-27T13:00:00Z", "hasta": "2026-09-27T15:00:00Z"}, [3, 2]),
    ],
)
async def test_filtros_de_alarmas(
    dentro: httpx.AsyncClient,
    db: AsyncSession,
    datos: Datos,
    casa: models.Casa,
    params: dict,
    esperados: list[int],
) -> None:
    await alarmas_de_prueba(db, casa, await datos.usuario("laura@ejemplo.com"))
    r = await dentro.get(f"/api/v1/casas/{casa.id}/alarmas", params=params)
    assert r.status_code == 200, r.text
    assert [alarma["id"] for alarma in r.json()["items"]] == esperados


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 101},
        {"limit": 0},
        {"nodo": 5},
        {"tipo": "INCENDIO"},
        {"desde": "2026-09-27T14:00:00"},  # sin zona horaria: ambiguo
        {"antes_de_id": "x"},
    ],
)
async def test_parametros_invalidos_de_alarmas(
    dentro: httpx.AsyncClient, casa: models.Casa, params: dict
) -> None:
    r = await dentro.get(f"/api/v1/casas/{casa.id}/alarmas", params=params)
    assert r.status_code == 400
    assert r.json()["detail"]["codigo"] == "solicitud_invalida"


# ------------------------------------------------------------------ eventos
async def test_eventos_paginados_y_filtrados(
    dentro: httpx.AsyncClient, db: AsyncSession, datos: Datos, casa: models.Casa
) -> None:
    laura = await datos.usuario("laura@ejemplo.com", nombre="Laura")
    for minuto in range(5):
        db.add(
            models.Evento(
                casa_id=casa.id,
                ocurrido_en=INICIO + timedelta(minutes=minuto),
                origen="usuario" if minuto == 1 else "backend",
                usuario_id=laura.id if minuto == 1 else None,
                nodo_id=2,
                tipo="alarma" if minuto % 2 == 0 else "info",
                texto=f"evento {minuto}",
                es_alarma=minuto % 2 == 0,
            )
        )
    await db.commit()
    ruta = f"/api/v1/casas/{casa.id}/eventos"

    pagina = (await dentro.get(ruta, params={"limit": 3})).json()
    assert [e["texto"] for e in pagina["items"]] == ["evento 4", "evento 3", "evento 2"]
    siguiente = (await dentro.get(ruta, params={"antes_de_id": pagina["siguiente"]})).json()
    assert [e["texto"] for e in siguiente["items"]] == ["evento 1", "evento 0"]
    assert siguiente["siguiente"] is None
    assert siguiente["items"][0]["usuario"] == {"id": laura.id, "nombre": "Laura"}
    assert siguiente["items"][0]["origen"] == "usuario"

    alarmas = (await dentro.get(ruta, params={"solo_alarmas": "true"})).json()["items"]
    assert [e["texto"] for e in alarmas] == ["evento 4", "evento 2", "evento 0"]
    tramo = await dentro.get(
        ruta, params={"desde": "2026-09-27T12:01:00Z", "hasta": "2026-09-27T12:03:00Z"}
    )
    assert [e["texto"] for e in tramo.json()["items"]] == ["evento 2", "evento 1"]
    assert (await dentro.get(ruta, params={"limit": 201})).status_code == 400
