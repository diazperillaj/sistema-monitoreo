"""Invitaciones (§8.2): el flujo completo, un solo uso, vencimiento y permisos."""

from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.auth import ahora, hash_token
from tests.ayudas import ORIGEN, CrearCliente, Datos, Entrar


@pytest.fixture
async def casa(datos: Datos) -> models.Casa:
    """Casa de la abuela: Ana es admin y Beto cuidador."""
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    beto = await datos.usuario("beto@ejemplo.com", nombre="Beto")
    casa = await datos.casa("casa-abuela", "Casa de la abuela")
    await datos.miembro(ana, casa, "admin")
    await datos.miembro(beto, casa, "cuidador")
    return casa


async def invitar(
    api: httpx.AsyncClient, entrar: Entrar, casa: models.Casa, **cuerpo: object
) -> str:
    """Ana crea una invitación y devuelve el token del enlace."""
    await entrar(api, "ana@ejemplo.com")
    r = await api.post(f"/api/v1/casas/{casa.id}/invitaciones", json={"rol": "cuidador"} | cuerpo)
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert url.startswith(f"{ORIGEN}/invitacion/")
    return url.rsplit("/", 1)[1]


NUEVA = {"nombre": "Tomás", "email": "Tomas@Ejemplo.com", "clave": "una clave larga"}


async def test_flujo_completo_sin_cuenta(
    api: httpx.AsyncClient,
    nuevo_cliente: CrearCliente,
    entrar: Entrar,
    casa: models.Casa,
    db: AsyncSession,
) -> None:
    token = await invitar(api, entrar, casa, email="tomas@ejemplo.com")
    # En la base solo queda el hash del token (§8.2)
    guardada = await db.scalar(select(models.Invitacion))
    assert guardada is not None and guardada.token_hash == hash_token(token)
    assert token not in guardada.token_hash

    invitado = nuevo_cliente()
    r = await invitado.get(f"/api/v1/invitaciones/{token}")
    assert r.status_code == 200
    assert r.json() == {
        "casa_nombre": "Casa de la abuela",
        "rol": "cuidador",
        "email": "tomas@ejemplo.com",
    }

    r = await invitado.post(f"/api/v1/invitaciones/{token}/aceptar", json=NUEVA)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "tomas@ejemplo.com"  # en minúsculas
    assert "sesion" in r.cookies  # entra de una, sin pasar por el login

    yo = (await invitado.get("/api/v1/auth/yo")).json()
    assert yo["usuario"]["nombre"] == "Tomás"
    assert yo["casas"] == [{"id": casa.id, "nombre": "Casa de la abuela", "rol": "cuidador"}]

    # Ya no figura entre las vigentes, y el historial cuenta quién entró
    assert (await api.get(f"/api/v1/casas/{casa.id}/invitaciones")).json() == []
    eventos = (await api.get(f"/api/v1/casas/{casa.id}/eventos")).json()["items"]
    assert eventos[0]["texto"] == "Tomás se unió a la casa como cuidador"


async def test_un_enlace_sirve_una_sola_vez(
    api: httpx.AsyncClient, nuevo_cliente: CrearCliente, entrar: Entrar, casa: models.Casa
) -> None:
    token = await invitar(api, entrar, casa)
    assert (
        await nuevo_cliente().post(f"/api/v1/invitaciones/{token}/aceptar", json=NUEVA)
    ).status_code == 200
    otra = NUEVA | {"email": "otra@ejemplo.com"}
    segundo = nuevo_cliente()
    for r in (
        await segundo.post(f"/api/v1/invitaciones/{token}/aceptar", json=otra),
        await segundo.get(f"/api/v1/invitaciones/{token}"),
    ):
        assert r.status_code == 409
        assert r.json()["detail"]["codigo"] == "invitacion_usada"


async def test_un_enlace_vencido(
    api: httpx.AsyncClient,
    nuevo_cliente: CrearCliente,
    entrar: Entrar,
    casa: models.Casa,
    db: AsyncSession,
) -> None:
    token = await invitar(api, entrar, casa)
    await db.execute(update(models.Invitacion).values(expira_en=ahora() - timedelta(minutes=1)))
    await db.commit()
    invitado = nuevo_cliente()
    for r in (
        await invitado.get(f"/api/v1/invitaciones/{token}"),
        await invitado.post(f"/api/v1/invitaciones/{token}/aceptar", json=NUEVA),
    ):
        assert r.status_code == 410
        assert r.json()["detail"]["codigo"] == "invitacion_vencida"


async def test_un_enlace_inexistente(nuevo_cliente: CrearCliente, casa: models.Casa) -> None:
    r = await nuevo_cliente().get("/api/v1/invitaciones/no-existe")
    assert r.status_code == 404


async def test_quien_ya_tiene_cuenta_se_une_con_ella(
    api: httpx.AsyncClient,
    nuevo_cliente: CrearCliente,
    entrar: Entrar,
    casa: models.Casa,
    datos: Datos,
    db: AsyncSession,
) -> None:
    carla = await datos.usuario("carla@ejemplo.com", nombre="Carla")
    otra_casa = await datos.casa("casa-carla", "Casa de Carla")
    await datos.miembro(carla, otra_casa, "admin")
    token = await invitar(api, entrar, casa, rol="admin")

    invitada = nuevo_cliente()
    await entrar(invitada, "carla@ejemplo.com")
    r = await invitada.post(f"/api/v1/invitaciones/{token}/aceptar", json={})
    assert r.status_code == 200
    assert r.json()["id"] == carla.id
    casas = {c["nombre"]: c["rol"] for c in (await invitada.get("/api/v1/auth/yo")).json()["casas"]}
    assert casas == {"Casa de la abuela": "admin", "Casa de Carla": "admin"}
    assert len((await db.scalars(select(models.Usuario))).all()) == 3  # no se creó otra cuenta


async def test_con_cuenta_existente_pero_sin_sesion(
    api: httpx.AsyncClient, nuevo_cliente: CrearCliente, entrar: Entrar, casa: models.Casa
) -> None:
    token = await invitar(api, entrar, casa)
    invitado = nuevo_cliente()
    r = await invitado.post(
        f"/api/v1/invitaciones/{token}/aceptar", json=NUEVA | {"email": "beto@ejemplo.com"}
    )
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "email_en_uso"
    # El enlace sigue sirviendo: Beto puede entrar con su cuenta y abrirlo de nuevo
    assert (await invitado.get(f"/api/v1/invitaciones/{token}")).status_code == 200


async def test_sin_sesion_pide_nombre_email_y_clave(
    api: httpx.AsyncClient, nuevo_cliente: CrearCliente, entrar: Entrar, casa: models.Casa
) -> None:
    token = await invitar(api, entrar, casa)
    r = await nuevo_cliente().post(f"/api/v1/invitaciones/{token}/aceptar", json={})
    assert r.status_code == 400
    assert r.json()["detail"]["campos"] == ["nombre", "email", "clave"]
    corta = await nuevo_cliente().post(
        f"/api/v1/invitaciones/{token}/aceptar", json=NUEVA | {"clave": "corta"}
    )
    assert corta.status_code == 400  # mínimo 10 caracteres (§12.1)


async def test_el_cuidador_no_invita(
    api: httpx.AsyncClient, entrar: Entrar, casa: models.Casa
) -> None:
    await entrar(api, "beto@ejemplo.com")
    r = await api.post(f"/api/v1/casas/{casa.id}/invitaciones", json={"rol": "cuidador"})
    assert r.status_code == 403
    assert (await api.get(f"/api/v1/casas/{casa.id}/invitaciones")).status_code == 403


async def test_anular_un_enlace(
    api: httpx.AsyncClient, nuevo_cliente: CrearCliente, entrar: Entrar, casa: models.Casa
) -> None:
    token = await invitar(api, entrar, casa, email="tomas@ejemplo.com")
    [vigente] = (await api.get(f"/api/v1/casas/{casa.id}/invitaciones")).json()
    assert vigente["email"] == "tomas@ejemplo.com"
    assert vigente["creada_por"]["nombre"] == "Ana"
    r = await api.delete(f"/api/v1/casas/{casa.id}/invitaciones/{vigente['id']}")
    assert r.status_code == 204
    assert (await nuevo_cliente().get(f"/api/v1/invitaciones/{token}")).status_code == 404
    otra = await api.delete(f"/api/v1/casas/{casa.id}/invitaciones/{vigente['id']}")
    assert otra.status_code == 404


async def test_la_cuenta_nueva_entra_con_su_clave(
    api: httpx.AsyncClient, nuevo_cliente: CrearCliente, entrar: Entrar, casa: models.Casa
) -> None:
    token = await invitar(api, entrar, casa)
    await nuevo_cliente().post(f"/api/v1/invitaciones/{token}/aceptar", json=NUEVA)
    otro_celular = nuevo_cliente()
    await entrar(otro_celular, "tomas@ejemplo.com", NUEVA["clave"])  # falla si no es 200


async def test_limite_de_intentos_en_invitaciones(
    nuevo_cliente: CrearCliente, casa: models.Casa
) -> None:
    """10 por minuto por IP (§12.4): nadie adivina enlaces a fuerza de intentos."""
    cliente = nuevo_cliente()
    respuestas = [await cliente.get(f"/api/v1/invitaciones/intento-{i}") for i in range(11)]
    assert [r.status_code for r in respuestas[:10]] == [404] * 10
    assert respuestas[10].status_code == 429
    assert respuestas[10].json()["detail"]["codigo"] == "demasiados_intentos"
