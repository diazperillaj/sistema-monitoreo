"""GET /api/v1/salud (§8.8)."""

import httpx

from app import __version__


async def test_salud_con_la_base_disponible(api: httpx.AsyncClient) -> None:
    r = await api.get("/api/v1/salud")
    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "db": "ok",
        "mqtt": "desconectado",  # el cliente MQTT llega en F2
        "telegram": "desactivado",
        "version": __version__,
    }
    assert r.headers["cache-control"] == "no-store"


async def test_salud_sin_base_responde_503(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/api/v1/salud")
    assert r.status_code == 503
    assert r.json()["ok"] is False
    assert r.json()["db"] == "error"
