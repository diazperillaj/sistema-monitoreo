"""Casas y ajustes (§8.3)."""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.auth import ahora
from tests.ayudas import Datos, Entrar

CASAS = "/api/v1/casas"


@pytest.fixture
async def superadmin(api: httpx.AsyncClient, datos: Datos, entrar: Entrar) -> httpx.AsyncClient:
    await datos.usuario("jp@ejemplo.com", superadmin=True)
    await entrar(api, "jp@ejemplo.com")
    return api


async def test_crear_casa_con_los_ajustes_por_defecto(superadmin: httpx.AsyncClient) -> None:
    r = await superadmin.post(
        CASAS, json={"codigo": "casa-abuela-x7k2", "nombre": " Casa de la abuela "}
    )
    assert r.status_code == 201
    casa = r.json()
    assert (casa["codigo"], casa["nombre"]) == ("casa-abuela-x7k2", "Casa de la abuela")
    assert casa["ajustes"] == {
        "recordatorio_min": 5,
        "recordatorio_conexion_min": 60,
        "minutos_central_caida": 1,
        "avisar_nodo_sin_conexion": True,
        "avisar_resueltas": True,
    }
    assert (await superadmin.get(f"{CASAS}/{casa['id']}")).json() == casa


@pytest.mark.parametrize("codigo", ["Casa-Abuela", "abc", "casa abuela", "backend_api", "x" * 41])
async def test_codigo_invalido(superadmin: httpx.AsyncClient, codigo: str) -> None:
    r = await superadmin.post(CASAS, json={"codigo": codigo, "nombre": "Casa"})
    assert r.status_code == 400
    assert r.json()["detail"]["codigo"] == "solicitud_invalida"
    assert r.json()["detail"]["campos"] == ["codigo"]


async def test_codigo_repetido(superadmin: httpx.AsyncClient) -> None:
    await superadmin.post(CASAS, json={"codigo": "casa-abuela", "nombre": "Una"})
    r = await superadmin.post(CASAS, json={"codigo": "casa-abuela", "nombre": "Otra"})
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "codigo_en_uso"


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"recordatorio_min": -1}, "recordatorio_min"),
        ({"recordatorio_conexion_min": 1441}, "recordatorio_conexion_min"),
        ({"minutos_central_caida": 0}, "minutos_central_caida"),
        ({"avisar_resueltas": "tal vez"}, "avisar_resueltas"),
    ],
)
async def test_ajustes_invalidos(
    superadmin: httpx.AsyncClient, cambio: dict[str, Any], campo: str
) -> None:
    casa = (await superadmin.post(CASAS, json={"codigo": "casa-ajustes", "nombre": "Casa"})).json()
    r = await superadmin.patch(f"{CASAS}/{casa['id']}/ajustes", json=cambio)
    assert r.status_code == 400
    assert r.json()["detail"]["campos"] == [campo]


async def test_los_ajustes_cambian_solo_lo_enviado(superadmin: httpx.AsyncClient) -> None:
    casa = (await superadmin.post(CASAS, json={"codigo": "casa-ajustes", "nombre": "Casa"})).json()
    r = await superadmin.patch(
        f"{CASAS}/{casa['id']}/ajustes",
        json={"recordatorio_conexion_min": 120, "avisar_resueltas": None},
    )
    assert r.status_code == 200
    assert r.json() == casa["ajustes"] | {"recordatorio_conexion_min": 120}


async def test_la_lista_muestra_conexion_y_alarmas_abiertas(
    api: httpx.AsyncClient, db: AsyncSession, datos: Datos, entrar: Entrar
) -> None:
    ana = await datos.usuario("ana@ejemplo.com")
    casa = await datos.casa("casa-abuela", "Casa de la abuela")
    await datos.miembro(ana, casa, "cuidador")
    momento = ahora()
    db.add(models.EstadoActual(casa_id=casa.id, online=True))
    db.add_all(
        [
            models.Alarma(casa_id=casa.id, nodo_id=2, tipo="SIN_MOVIMIENTO", inicio_en=momento),
            models.Alarma(
                casa_id=casa.id, nodo_id=None, tipo="CENTRAL_DESCONECTADA", inicio_en=momento
            ),
            models.Alarma(
                casa_id=casa.id, nodo_id=3, tipo="AGUA", inicio_en=momento, fin_en=momento
            ),
        ]
    )
    await db.commit()
    await entrar(api, "ana@ejemplo.com")
    assert (await api.get(CASAS)).json() == [
        {
            "id": casa.id,
            "codigo": "casa-abuela",
            "nombre": "Casa de la abuela",
            "rol": "cuidador",
            "online": True,
            "alarmas_abiertas": 2,
        }
    ]
