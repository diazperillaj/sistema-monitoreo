"""Envío por WebSocket a los clientes de una casa (§9)."""

import asyncio
import json

import pytest

from app.services import ws_hub
from app.services.ws_hub import HubWs


class WsFalso:
    def __init__(self, *, caido: bool = False, lento: bool = False) -> None:
        self.caido = caido
        self.lento = lento
        self.recibidos: list[dict] = []

    async def send_text(self, texto: str) -> None:
        if self.caido:
            raise RuntimeError("conexión cerrada")
        if self.lento:
            await asyncio.sleep(10)
        self.recibidos.append(json.loads(texto))


async def test_emite_solo_a_los_clientes_de_esa_casa() -> None:
    hub = HubWs()
    uno, otro, ajeno = WsFalso(), WsFalso(), WsFalso()
    hub.entrar(1, uno)  # type: ignore[arg-type]
    hub.entrar(1, otro)  # type: ignore[arg-type]
    hub.entrar(2, ajeno)  # type: ignore[arg-type]

    await hub.emitir(1, {"tipo": "evento", "texto": "Baño"})
    assert uno.recibidos == otro.recibidos == [{"tipo": "evento", "texto": "Baño"}]
    assert ajeno.recibidos == []


async def test_saca_a_los_clientes_caidos_o_lentos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws_hub, "ESPERA_MAXIMA_S", 0.05)
    hub = HubWs()
    sano, caido, lento = WsFalso(), WsFalso(caido=True), WsFalso(lento=True)
    for ws in (sano, caido, lento):
        hub.entrar(1, ws)  # type: ignore[arg-type]

    await hub.emitir(1, {"tipo": "pong"})
    await hub.emitir(1, {"tipo": "pong"})
    assert sano.recibidos == [{"tipo": "pong"}, {"tipo": "pong"}]
    assert hub.hay_clientes(1)

    hub.salir(1, sano)  # type: ignore[arg-type]
    assert not hub.hay_clientes(1)  # los otros dos ya habían salido
    await hub.emitir(1, {"tipo": "pong"})  # sin clientes no pasa nada
