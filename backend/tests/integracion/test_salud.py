"""GET /api/v1/salud (§8.8)."""

import httpx

from app import __version__


async def test_salud_responde_ok(cliente: httpx.AsyncClient) -> None:
    r = await cliente.get("/api/v1/salud")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": __version__}
    assert r.headers["cache-control"] == "no-store"
