"""Miembros (§8.6): ver, cambiar de rol y quitar, sin dejar la casa sin admin."""

import httpx
import pytest

from app import models
from tests.ayudas import CrearCliente, Datos, Entrar


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    """Ana es la única admin; Beto y Camila son cuidadores."""
    casa = await datos.casa("casa-abuela", "Casa de la abuela")
    for email, nombre, rol in (
        ("ana@ejemplo.com", "Ana", "admin"),
        ("beto@ejemplo.com", "Beto", "cuidador"),
        ("camila@ejemplo.com", "Camila", "cuidador"),
    ):
        await datos.miembro(await datos.usuario(email, nombre=nombre), casa, rol)
    return casa


async def ids(api: httpx.AsyncClient, casa: models.Casa) -> dict[str, int]:
    miembros = (await api.get(f"/api/v1/casas/{casa.id}/miembros")).json()
    return {m["usuario"]["nombre"]: m["usuario"]["id"] for m in miembros}


async def test_cualquier_miembro_ve_la_lista(
    api: httpx.AsyncClient, entrar: Entrar, casa: models.Casa
) -> None:
    await entrar(api, "beto@ejemplo.com")
    r = await api.get(f"/api/v1/casas/{casa.id}/miembros")
    assert r.status_code == 200
    assert [(m["usuario"]["nombre"], m["rol"]) for m in r.json()] == [
        ("Ana", "admin"),  # primero los admins
        ("Beto", "cuidador"),
        ("Camila", "cuidador"),
    ]
    assert r.json()[0]["usuario"]["email"] == "ana@ejemplo.com"


async def test_el_admin_cambia_el_rol(
    api: httpx.AsyncClient, entrar: Entrar, casa: models.Casa
) -> None:
    await entrar(api, "ana@ejemplo.com")
    beto = (await ids(api, casa))["Beto"]
    r = await api.patch(f"/api/v1/casas/{casa.id}/miembros/{beto}", json={"rol": "admin"})
    assert r.status_code == 200
    assert r.json()["rol"] == "admin"
    eventos = (await api.get(f"/api/v1/casas/{casa.id}/eventos")).json()["items"]
    assert eventos[0]["texto"] == "Ana hizo admin a Beto"


async def test_la_casa_nunca_se_queda_sin_admin(
    api: httpx.AsyncClient, entrar: Entrar, casa: models.Casa
) -> None:
    await entrar(api, "ana@ejemplo.com")
    personas = await ids(api, casa)
    ruta = f"/api/v1/casas/{casa.id}/miembros/{personas['Ana']}"
    for r in (await api.patch(ruta, json={"rol": "cuidador"}), await api.delete(ruta)):
        assert r.status_code == 409
        assert r.json()["detail"]["codigo"] == "ultimo_admin"
    # Con otra admin, Ana sí puede salir
    await api.patch(f"/api/v1/casas/{casa.id}/miembros/{personas['Camila']}", json={"rol": "admin"})
    assert (await api.delete(ruta)).status_code == 204
    assert (await api.get(f"/api/v1/casas/{casa.id}/miembros")).status_code == 403


async def test_quien_sale_deja_de_ver_la_casa(
    api: httpx.AsyncClient, nuevo_cliente: CrearCliente, entrar: Entrar, casa: models.Casa
) -> None:
    beto = nuevo_cliente()
    await entrar(beto, "beto@ejemplo.com")
    assert (await beto.get(f"/api/v1/casas/{casa.id}/estado")).status_code == 200

    await entrar(api, "ana@ejemplo.com")
    r = await api.delete(f"/api/v1/casas/{casa.id}/miembros/{(await ids(api, casa))['Beto']}")
    assert r.status_code == 204
    assert (await beto.get(f"/api/v1/casas/{casa.id}/estado")).status_code == 403
    assert (await beto.get("/api/v1/auth/yo")).json()["casas"] == []
    eventos = (await api.get(f"/api/v1/casas/{casa.id}/eventos")).json()["items"]
    assert eventos[0]["texto"] == "Ana quitó a Beto de la casa"


async def test_el_cuidador_no_cambia_nada(
    api: httpx.AsyncClient, entrar: Entrar, casa: models.Casa
) -> None:
    await entrar(api, "beto@ejemplo.com")
    camila = (await ids(api, casa))["Camila"]
    ruta = f"/api/v1/casas/{casa.id}/miembros/{camila}"
    assert (await api.patch(ruta, json={"rol": "admin"})).status_code == 403
    assert (await api.delete(ruta)).status_code == 403


async def test_alguien_que_no_es_miembro(
    api: httpx.AsyncClient, entrar: Entrar, casa: models.Casa, datos: Datos
) -> None:
    ajena = await datos.usuario("zoe@ejemplo.com")
    await entrar(api, "ana@ejemplo.com")
    r = await api.patch(f"/api/v1/casas/{casa.id}/miembros/{ajena.id}", json={"rol": "admin"})
    assert r.status_code == 404
