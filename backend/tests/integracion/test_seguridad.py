"""CSRF por Origin (§12.3) y límites de intentos (§12.4)."""

import httpx

from tests.ayudas import CLAVE, CrearCliente, Datos

LOGIN = "/api/v1/auth/login"


async def test_un_post_sin_origin_se_rechaza(nuevo_cliente: CrearCliente, datos: Datos) -> None:
    await datos.usuario("ana@ejemplo.com")
    r = await nuevo_cliente(origen=None).post(
        LOGIN, json={"email": "ana@ejemplo.com", "clave": CLAVE}
    )
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "origen_invalido"


async def test_un_post_desde_otro_sitio_se_rechaza(
    nuevo_cliente: CrearCliente, datos: Datos
) -> None:
    await datos.usuario("ana@ejemplo.com")
    cliente = nuevo_cliente(origen="https://sitio-malicioso.test")
    r = await cliente.post(LOGIN, json={"email": "ana@ejemplo.com", "clave": CLAVE})
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "origen_invalido"


async def test_un_get_no_necesita_origin(nuevo_cliente: CrearCliente) -> None:
    assert (await nuevo_cliente(origen=None).get("/api/v1/salud")).status_code == 200


async def test_los_rechazos_tambien_llevan_las_cabeceras_de_seguridad(
    nuevo_cliente: CrearCliente,
) -> None:
    r = await nuevo_cliente(origen=None).post(LOGIN, json={})
    assert r.status_code == 403
    assert r.headers["cache-control"] == "no-store"
    assert "content-security-policy" in r.headers


async def test_login_limitado_por_ip_y_email(api: httpx.AsyncClient, datos: Datos) -> None:
    await datos.usuario("ana@ejemplo.com")
    for _ in range(5):
        r = await api.post(LOGIN, json={"email": "ana@ejemplo.com", "clave": "no-es-la-clave"})
        assert r.status_code == 401
    r = await api.post(LOGIN, json={"email": "ana@ejemplo.com", "clave": CLAVE})  # ni con la buena
    assert r.status_code == 429
    assert r.json()["detail"]["codigo"] == "demasiados_intentos"
    assert int(r.headers["retry-after"]) > 0
    # Otro email desde la misma IP todavía puede intentar
    r = await api.post(LOGIN, json={"email": "beto@ejemplo.com", "clave": CLAVE})
    assert r.status_code == 401


async def test_login_limitado_por_ip_en_la_hora(api: httpx.AsyncClient) -> None:
    for i in range(20):
        r = await api.post(LOGIN, json={"email": f"persona{i}@ejemplo.com", "clave": CLAVE})
        assert r.status_code == 401
    r = await api.post(LOGIN, json={"email": "una-mas@ejemplo.com", "clave": CLAVE})
    assert r.status_code == 429


async def test_limite_general_por_ip(api: httpx.AsyncClient) -> None:
    codigos = [(await api.get("/api/v1/auth/yo")).status_code for _ in range(80)]
    assert codigos[:40] == [401] * 40  # la ráfaga de 40 pasa
    assert 429 in codigos  # después, más de 10 por segundo se frena
