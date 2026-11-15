"""Permisos por rol y por casa (§8, §12.5): nadie accede a una casa ajena."""

import httpx
import pytest

from app import models
from tests.ayudas import Datos, Entrar


async def dos_casas(datos: Datos) -> tuple[models.Casa, models.Casa]:
    """Casa A: Ana (admin) y Beto (cuidador). Casa B: Carla (admin). JP es superadmin."""
    ana = await datos.usuario("ana@ejemplo.com")
    beto = await datos.usuario("beto@ejemplo.com")
    carla = await datos.usuario("carla@ejemplo.com")
    await datos.usuario("jp@ejemplo.com", superadmin=True)
    a = await datos.casa("casa-a", "Casa A")
    b = await datos.casa("casa-b", "Casa B")
    await datos.miembro(ana, a, "admin")
    await datos.miembro(beto, a, "cuidador")
    await datos.miembro(carla, b, "admin")
    return a, b


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("GET", "/casas/{id}", None),
        ("PATCH", "/casas/{id}", {"nombre": "Mía"}),
        ("GET", "/casas/{id}/ajustes", None),
        ("PATCH", "/casas/{id}/ajustes", {"recordatorio_min": 10}),
        ("GET", "/casas/{id}/estado", None),
        ("GET", "/casas/{id}/alarmas", None),
        ("GET", "/casas/{id}/eventos", None),
        ("POST", "/casas/{id}/comandos", {"nodo": 2, "accion": "silenciar"}),
        ("POST", "/casas/{id}/comandos/silenciar-todo", None),
        ("GET", "/casas/{id}/comandos", None),
        ("GET", "/casas/{id}/comandos/1", None),
        ("GET", "/casas/{id}/miembros", None),
        ("PATCH", "/casas/{id}/miembros/1", {"rol": "admin"}),
        ("DELETE", "/casas/{id}/miembros/1", None),
        ("GET", "/casas/{id}/invitaciones", None),
        ("POST", "/casas/{id}/invitaciones", {"rol": "cuidador"}),
        ("DELETE", "/casas/{id}/invitaciones/1", None),
        ("GET", "/casas/{id}/resumen", None),
        (
            "GET",
            "/casas/{id}/lecturas?nodo=4&metrica=gas&desde=2026-09-27T12:00:00Z&hasta=2026-09-28T12:00:00Z",
            None,
        ),
    ],
)
async def test_nadie_accede_a_una_casa_ajena(
    api: httpx.AsyncClient,
    datos: Datos,
    entrar: Entrar,
    metodo: str,
    ruta: str,
    cuerpo: dict | None,
) -> None:
    _, b = await dos_casas(datos)
    await entrar(api, "ana@ejemplo.com")
    r = await api.request(metodo, "/api/v1" + ruta.format(id=b.id), json=cuerpo)
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "sin_permiso"


async def test_la_lista_solo_trae_las_casas_propias(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    a, _ = await dos_casas(datos)
    await entrar(api, "ana@ejemplo.com")
    assert [casa["id"] for casa in (await api.get("/api/v1/casas")).json()] == [a.id]


async def test_el_cuidador_ve_pero_no_cambia(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    a, _ = await dos_casas(datos)
    await entrar(api, "beto@ejemplo.com")
    assert (await api.get(f"/api/v1/casas/{a.id}")).status_code == 200
    assert (await api.get(f"/api/v1/casas/{a.id}/ajustes")).status_code == 200
    assert (await api.patch(f"/api/v1/casas/{a.id}", json={"nombre": "Otra"})).status_code == 403
    r = await api.patch(f"/api/v1/casas/{a.id}/ajustes", json={"recordatorio_min": 1})
    assert r.status_code == 403


async def test_el_admin_cambia_su_casa(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    a, _ = await dos_casas(datos)
    await entrar(api, "ana@ejemplo.com")
    r = await api.patch(f"/api/v1/casas/{a.id}", json={"nombre": "  Casa de la abuela  "})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Casa de la abuela"
    r = await api.patch(f"/api/v1/casas/{a.id}/ajustes", json={"recordatorio_min": 10})
    assert r.json()["recordatorio_min"] == 10


async def test_el_superadmin_llega_a_todas_las_casas(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    a, b = await dos_casas(datos)
    await entrar(api, "jp@ejemplo.com")
    lista = (await api.get("/api/v1/casas")).json()
    assert [(casa["id"], casa["rol"]) for casa in lista] == [(a.id, "admin"), (b.id, "admin")]
    r = await api.patch(f"/api/v1/casas/{b.id}/ajustes", json={"avisar_resueltas": False})
    assert r.status_code == 200
    assert (await api.get("/api/v1/casas/9999")).status_code == 404


async def test_a_quien_no_es_superadmin_no_se_le_confirma_si_una_casa_existe(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    await dos_casas(datos)
    await entrar(api, "ana@ejemplo.com")
    assert (await api.get("/api/v1/casas/9999")).status_code == 403


async def test_solo_el_superadmin_crea_casas(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    await dos_casas(datos)
    await entrar(api, "ana@ejemplo.com")
    r = await api.post("/api/v1/casas", json={"codigo": "casa-nueva", "nombre": "Nueva"})
    assert r.status_code == 403


async def test_sin_sesion_no_hay_casas(api: httpx.AsyncClient) -> None:
    assert (await api.get("/api/v1/casas")).status_code == 401
