"""Frontend servido por FastAPI: respaldo SPA, 404 JSON de la API, caché y cabeceras (§6.7)."""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.web import archivo_del_build

CrearCliente = Callable[..., httpx.AsyncClient]
NO_ENCONTRADO = {"detail": {"codigo": "no_encontrado", "mensaje": "Ruta de la API inexistente."}}


async def test_inicio_sirve_index_sin_cache(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Monitoreo del hogar" in r.text
    assert r.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("ruta", ["/casa/1", "/casa/1/historial", "/invitacion/abc123", "/perfil"])
async def test_rutas_del_cliente_devuelven_index(cliente: httpx.AsyncClient, ruta: str) -> None:
    r = await cliente.get(ruta)
    assert r.status_code == 200
    assert "Monitoreo del hogar" in r.text
    assert r.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("GET", "/api/cualquier-cosa"),
        ("GET", "/api/estado"),  # la app local de la ESP32 no debe confundir este dominio (§3.4)
        ("POST", "/api/v1/no-existe"),
        ("DELETE", "/api/v1/casas/1/otra"),
    ],
)
async def test_api_inexistente_da_404_json(
    cliente: httpx.AsyncClient, metodo: str, ruta: str
) -> None:
    r = await cliente.request(metodo, ruta)
    assert r.status_code == 404
    assert r.json() == NO_ENCONTRADO
    assert r.headers["cache-control"] == "no-store"


async def test_websocket_por_http_da_404(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/ws/v1/casas/1")
    assert r.status_code == 404
    assert r.json()["detail"]["codigo"] == "no_encontrado"


async def test_assets_con_cache_inmutable(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/assets/index-abc123.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_asset_inexistente_no_devuelve_index(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/assets/index-viejo.js")
    assert r.status_code == 404
    assert r.headers["cache-control"] == "no-store"


async def test_iconos_con_cache_de_una_semana(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/icons/icon-192.png")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=604800"


@pytest.mark.parametrize(
    ("ruta", "contenido"),
    [("/sw.js", "addEventListener('push'"), ("/manifest.webmanifest", '"name"')],
)
async def test_service_worker_y_manifest_sin_cache(
    cliente: httpx.AsyncClient, ruta: str, contenido: str
) -> None:
    r = await cliente.get(ruta)
    assert r.status_code == 200
    assert contenido in r.text  # el archivo real, no el index.html del respaldo SPA
    assert r.headers["cache-control"] == "no-cache"


def test_no_se_sale_de_la_carpeta_del_build(frontend_compilado: Path) -> None:
    (frontend_compilado.parent / "secreto.txt").write_text("no debe verse", encoding="utf-8")
    assert archivo_del_build(frontend_compilado, "../secreto.txt") is None
    assert (
        archivo_del_build(frontend_compilado, "sw.js") == (frontend_compilado / "sw.js").resolve()
    )


async def test_cabeceras_de_seguridad_en_produccion(cliente: httpx.AsyncClient) -> None:
    h = (await cliente.get("/")).headers
    assert h["strict-transport-security"] == "max-age=31536000"
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert h["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    csp = h["content-security-policy"]
    assert "script-src 'self';" in csp
    assert "connect-src 'self' wss://alarma.test;" in csp
    assert "ws://localhost" not in csp
    assert csp.endswith("frame-ancestors 'none'")


async def test_desarrollo_sin_hsts_y_con_websocket_local(
    crear_cliente: CrearCliente, frontend_compilado: Path
) -> None:
    cliente = crear_cliente(
        entorno="desarrollo", dominio="localhost", directorio_frontend=frontend_compilado
    )
    h = (await cliente.get("/")).headers
    assert "strict-transport-security" not in h
    assert "connect-src 'self' wss://localhost ws://localhost:*;" in h["content-security-policy"]


async def test_sin_build_responde_503(crear_cliente: CrearCliente, tmp_path: Path) -> None:
    cliente = crear_cliente(directorio_frontend=tmp_path / "sin-build")
    r = await cliente.get("/")
    assert r.status_code == 503
    assert r.text == "Frontend no compilado."


async def test_docs_de_la_api_con_su_propia_csp(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/api/v1/docs")
    assert r.status_code == 200
    assert "https://cdn.jsdelivr.net" in r.headers["content-security-policy"]
