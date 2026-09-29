"""Conexiones WebSocket por casa y envío a todas ellas (§9).

Vive en memoria: por eso la API corre con un solo worker (§6.6).
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)
ESPERA_MAXIMA_S = 5  # un cliente lento no frena a los demás ni a la ingesta


class HubWs:
    def __init__(self) -> None:
        self._clientes: dict[int, set[WebSocket]] = defaultdict(set)

    def entrar(self, casa_id: int, ws: WebSocket) -> None:
        self._clientes[casa_id].add(ws)

    def salir(self, casa_id: int, ws: WebSocket) -> None:
        clientes = self._clientes.get(casa_id)
        if clientes is not None:
            clientes.discard(ws)
            if not clientes:
                del self._clientes[casa_id]

    def hay_clientes(self, casa_id: int) -> bool:
        return bool(self._clientes.get(casa_id))

    async def emitir(self, casa_id: int, mensaje: dict[str, Any]) -> None:
        clientes = list(self._clientes.get(casa_id, ()))
        if not clientes:
            return
        texto = json.dumps(mensaje, ensure_ascii=False)
        enviados = await asyncio.gather(*(self._enviar(ws, texto) for ws in clientes))
        for ws, enviado in zip(clientes, enviados, strict=True):
            if not enviado:
                self.salir(casa_id, ws)

    @staticmethod
    async def _enviar(ws: WebSocket, texto: str) -> bool:
        try:
            async with asyncio.timeout(ESPERA_MAXIMA_S):
                await ws.send_text(texto)
        except Exception:  # cliente caído o demasiado lento: se lo saca
            return False
        return True
