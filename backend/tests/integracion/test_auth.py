"""Autenticación y sesiones (§8.1, §12.1, §12.2)."""

from datetime import timedelta

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.auth import ahora
from tests.ayudas import CLAVE, CrearCliente, Datos, Entrar

LOGIN = "/api/v1/auth/login"
YO = "/api/v1/auth/yo"


async def test_login_entrega_una_cookie_segura(api: httpx.AsyncClient, datos: Datos) -> None:
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    r = await api.post(LOGIN, json={"email": "ana@ejemplo.com", "clave": CLAVE})
    assert r.status_code == 200
    assert r.json() == {
        "id": ana.id,
        "email": "ana@ejemplo.com",
        "nombre": "Ana",
        "es_superadmin": False,
    }
    cookie = r.headers["set-cookie"]
    for atributo in ("sesion=", "HttpOnly", "Secure", "SameSite=lax", "Path=/", "Max-Age=2592000"):
        assert atributo in cookie


async def test_el_email_no_distingue_mayusculas(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("ana@ejemplo.com")
    await entrar(api, "  ANA@Ejemplo.COM ")


async def test_no_revela_si_el_email_existe(api: httpx.AsyncClient, datos: Datos) -> None:
    await datos.usuario("ana@ejemplo.com")
    clave_mala = await api.post(
        LOGIN, json={"email": "ana@ejemplo.com", "clave": "otra-clave-cualquiera"}
    )
    sin_usuario = await api.post(LOGIN, json={"email": "nadie@ejemplo.com", "clave": CLAVE})
    assert clave_mala.status_code == sin_usuario.status_code == 401
    assert clave_mala.json() == sin_usuario.json()
    assert clave_mala.json()["detail"]["codigo"] == "credenciales_invalidas"


async def test_un_usuario_inactivo_no_entra(api: httpx.AsyncClient, datos: Datos) -> None:
    await datos.usuario("ana@ejemplo.com", activo=False)
    r = await api.post(LOGIN, json={"email": "ana@ejemplo.com", "clave": CLAVE})
    assert r.status_code == 401


async def test_sin_sesion_da_401(api: httpx.AsyncClient) -> None:
    r = await api.get(YO)
    assert r.status_code == 401
    assert r.json()["detail"]["codigo"] == "no_autenticado"


async def test_yo_trae_sus_casas_con_su_rol(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    ana = await datos.usuario("ana@ejemplo.com", nombre="Ana")
    abuela = await datos.casa("casa-abuela", "Casa de la abuela")
    tia = await datos.casa("casa-tia", "Apartamento de la tía")
    await datos.casa("casa-ajena", "Casa ajena")
    await datos.miembro(ana, abuela, "cuidador")
    await datos.miembro(ana, tia, "admin")
    await entrar(api, "ana@ejemplo.com")
    assert (await api.get(YO)).json() == {
        "usuario": {
            "id": ana.id,
            "email": "ana@ejemplo.com",
            "nombre": "Ana",
            "es_superadmin": False,
        },
        "casas": [
            {"id": tia.id, "nombre": "Apartamento de la tía", "rol": "admin"},
            {"id": abuela.id, "nombre": "Casa de la abuela", "rol": "cuidador"},
        ],
    }


async def test_el_superadmin_ve_todas_las_casas_como_admin(
    api: httpx.AsyncClient, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("jp@ejemplo.com", superadmin=True)
    casa = await datos.casa("casa-abuela", "Casa de la abuela")
    await entrar(api, "jp@ejemplo.com")
    yo = (await api.get(YO)).json()
    assert yo["usuario"]["es_superadmin"] is True
    assert yo["casas"] == [{"id": casa.id, "nombre": "Casa de la abuela", "rol": "admin"}]


async def test_logout_cierra_la_sesion(
    api: httpx.AsyncClient, db: AsyncSession, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("ana@ejemplo.com")
    await entrar(api, "ana@ejemplo.com")
    r = await api.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert "Max-Age=0" in r.headers["set-cookie"]
    assert (await api.get(YO)).status_code == 401
    assert await db.scalar(select(func.count()).select_from(models.Sesion)) == 0


async def test_una_sesion_vencida_da_401(
    api: httpx.AsyncClient, db: AsyncSession, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("ana@ejemplo.com")
    await entrar(api, "ana@ejemplo.com")
    await db.execute(update(models.Sesion).values(expira_en=ahora() - timedelta(minutes=1)))
    await db.commit()
    assert (await api.get(YO)).status_code == 401


async def test_renovacion_deslizante(
    api: httpx.AsyncClient, db: AsyncSession, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("ana@ejemplo.com")
    await entrar(api, "ana@ejemplo.com")
    assert "set-cookie" not in (await api.get(YO)).headers  # recién usada: no se renueva

    await db.execute(
        update(models.Sesion).values(
            ultimo_uso_en=ahora() - timedelta(days=2), expira_en=ahora() + timedelta(days=1)
        )
    )
    await db.commit()
    r = await api.get(YO)
    assert r.status_code == 200
    assert "Max-Age=2592000" in r.headers["set-cookie"]  # la cookie también se renueva
    db.expire_all()
    sesion = await db.scalar(select(models.Sesion))
    assert sesion is not None
    assert sesion.expira_en > ahora() + timedelta(days=29)


async def test_cambiar_la_clave_cierra_las_demas_sesiones(
    nuevo_cliente: CrearCliente, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("ana@ejemplo.com")
    este, otro = nuevo_cliente(), nuevo_cliente()
    await entrar(este, "ana@ejemplo.com")
    await entrar(otro, "ana@ejemplo.com")
    cambio = "/api/v1/auth/cambiar-clave"

    r = await este.post(
        cambio, json={"clave_actual": "no-es-esta", "clave_nueva": "una-clave-nueva-larga"}
    )
    assert r.status_code == 400
    assert r.json()["detail"]["codigo"] == "clave_incorrecta"
    r = await este.post(cambio, json={"clave_actual": CLAVE, "clave_nueva": "corta"})
    assert r.status_code == 400
    assert r.json()["detail"]["campos"] == ["clave_nueva"]

    r = await este.post(
        cambio, json={"clave_actual": CLAVE, "clave_nueva": "una-clave-nueva-larga"}
    )
    assert r.status_code == 204
    assert (await este.get(YO)).status_code == 200  # la sesión desde la que se cambió sigue
    assert (await otro.get(YO)).status_code == 401
    nuevo = nuevo_cliente()
    assert (
        await nuevo.post(LOGIN, json={"email": "ana@ejemplo.com", "clave": CLAVE})
    ).status_code == 401
    await entrar(nuevo, "ana@ejemplo.com", "una-clave-nueva-larga")


async def test_listar_y_cerrar_sesiones(
    nuevo_cliente: CrearCliente, datos: Datos, entrar: Entrar
) -> None:
    await datos.usuario("ana@ejemplo.com")
    await datos.usuario("beto@ejemplo.com")
    celular, computador, de_beto = nuevo_cliente(), nuevo_cliente(), nuevo_cliente()
    await entrar(celular, "ana@ejemplo.com")
    await entrar(computador, "ana@ejemplo.com")
    await entrar(de_beto, "beto@ejemplo.com")

    sesiones = (await computador.get("/api/v1/auth/sesiones")).json()
    assert len(sesiones) == 2
    assert [sesion["actual"] for sesion in sesiones].count(True) == 1
    assert {sesion["ip"] for sesion in sesiones} == {"127.0.0.1"}
    la_del_celular = next(sesion["id"] for sesion in sesiones if not sesion["actual"])

    la_de_beto = (await de_beto.get("/api/v1/auth/sesiones")).json()[0]["id"]
    assert (await computador.delete(f"/api/v1/auth/sesiones/{la_de_beto}")).status_code == 404

    assert (await computador.delete(f"/api/v1/auth/sesiones/{la_del_celular}")).status_code == 204
    assert (await celular.get(YO)).status_code == 401
    assert len((await computador.get("/api/v1/auth/sesiones")).json()) == 1
