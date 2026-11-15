"""Lecturas agregadas y resumen de alarmas (§7.4, §8.5)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.auth import ahora
from tests.ayudas import Datos, Entrar

INICIO = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    casa = await datos.casa("casa-abuela", "Casa de la abuela")
    await datos.miembro(ana, casa, "cuidador")
    return casa


@pytest.fixture
async def dentro(api: httpx.AsyncClient, casa: models.Casa, entrar: Entrar) -> httpx.AsyncClient:
    await entrar(api, "ana@ejemplo.com")
    return api


def consulta(**cambios: object) -> dict[str, object]:
    return {
        "nodo": 4,
        "metrica": "temperatura",
        "desde": INICIO.isoformat(),
        "hasta": (INICIO + timedelta(minutes=10)).isoformat(),
        "agregacion": "5m",
    } | cambios


async def test_promedio_por_intervalo(
    dentro: httpx.AsyncClient, casa: models.Casa, db: AsyncSession
) -> None:
    # Una lectura por minuto: 20.0, 21.0 … 29.0; más una de otra métrica y otra fuera del periodo
    db.add_all(
        [
            models.Lectura(
                casa_id=casa.id,
                nodo_id=4,
                metrica="temperatura",
                medido_en=INICIO + timedelta(minutes=i),
                valor=20.0 + i,
            )
            for i in range(10)
        ]
        + [
            models.Lectura(
                casa_id=casa.id, nodo_id=4, metrica="gas", medido_en=INICIO, valor=640.0
            ),
            models.Lectura(
                casa_id=casa.id,
                nodo_id=4,
                metrica="temperatura",
                medido_en=INICIO + timedelta(minutes=10),  # `hasta` no se incluye
                valor=99.0,
            ),
        ]
    )
    await db.commit()
    r = await dentro.get(f"/api/v1/casas/{casa.id}/lecturas", params=consulta())
    assert r.status_code == 200
    assert r.json() == [
        {"t": "2026-09-27T12:00:00Z", "valor": 22.0},
        {"t": "2026-09-27T12:05:00Z", "valor": 27.0},
    ]


async def test_sin_lecturas_la_lista_va_vacia(dentro: httpx.AsyncClient, casa: models.Casa) -> None:
    r = await dentro.get(
        f"/api/v1/casas/{casa.id}/lecturas", params=consulta(metrica="caudal", nodo=3)
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"hasta": INICIO.isoformat()}, "hasta"),  # periodo vacío
        ({"hasta": (INICIO + timedelta(days=30)).isoformat(), "agregacion": "1m"}, "agregacion"),
        ({"desde": "2026-09-27T12:00:00"}, "desde"),  # sin zona horaria: ambigua
        ({"metrica": "humedad"}, "metrica"),
    ],
)
async def test_consultas_invalidas(
    dentro: httpx.AsyncClient, casa: models.Casa, cambios: dict[str, object], campo: str
) -> None:
    r = await dentro.get(f"/api/v1/casas/{casa.id}/lecturas", params=consulta(**cambios))
    assert r.status_code == 400
    assert campo in r.json()["detail"]["campos"]


async def alarma(
    db: AsyncSession, casa: models.Casa, tipo: str, hace: timedelta, **campos: object
) -> None:
    inicio = ahora() - hace
    db.add(
        models.Alarma(
            casa_id=casa.id,
            nodo_id=None if tipo == "CENTRAL_DESCONECTADA" else 2,
            tipo=tipo,
            inicio_en=inicio,
            **campos,
        )
    )
    await db.commit()


async def test_resumen_de_la_semana(
    dentro: httpx.AsyncClient, casa: models.Casa, db: AsyncSession
) -> None:
    fin = timedelta(minutes=3)
    await alarma(db, casa, "SIN_MOVIMIENTO", timedelta(minutes=10))
    await alarma(
        db,
        casa,
        "SIN_MOVIMIENTO",
        timedelta(days=1),
        fin_en=ahora() - timedelta(days=1) + fin,
        cerrada_por="usuario",
    )
    await alarma(
        db,
        casa,
        "AGUA",
        timedelta(days=1),
        fin_en=ahora() - timedelta(days=1) + 2 * fin,
        cerrada_por="usuario",
    )
    await alarma(db, casa, "CENTRAL_DESCONECTADA", timedelta(days=2))
    await alarma(db, casa, "GAS", timedelta(days=30))  # fuera de la semana

    r = await dentro.get(f"/api/v1/casas/{casa.id}/resumen")
    assert r.status_code == 200
    resumen = r.json()
    assert resumen["dias"] == 7
    assert resumen["alarmas_por_tipo"] == {
        "SIN_MOVIMIENTO": 2,
        "AGUA": 1,
        "CENTRAL_DESCONECTADA": 1,
    }
    assert resumen["tiempo_medio_respuesta_s"] == pytest.approx(270, abs=1)  # (3 + 6) / 2 min
    por_dia = resumen["alarmas_por_dia"]
    assert len(por_dia) == 7  # también los días sin alarmas
    assert [(d["sensor"], d["conexion"]) for d in por_dia[-3:]] == [(0, 1), (2, 0), (1, 0)]
    assert sum(d["sensor"] + d["conexion"] for d in por_dia) == 4


async def test_resumen_sin_alarmas(dentro: httpx.AsyncClient, casa: models.Casa) -> None:
    resumen = (await dentro.get(f"/api/v1/casas/{casa.id}/resumen", params={"dias": 1})).json()
    assert resumen["alarmas_por_tipo"] == {}
    assert resumen["tiempo_medio_respuesta_s"] is None
    assert [(d["sensor"], d["conexion"]) for d in resumen["alarmas_por_dia"]] == [(0, 0)]
