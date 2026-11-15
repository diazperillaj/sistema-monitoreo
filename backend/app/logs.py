"""Logs en JSON por stdout (§16), también los de uvicorn."""

import json
import logging
import sys
from datetime import UTC, datetime


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos = {
            "t": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        if record.exc_info:
            datos["error"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def configurar_logs(nivel: str) -> None:
    """Idempotente: agrega el manejador JSON una sola vez y respeta los que ya existan."""
    raiz = logging.getLogger()
    if not any(isinstance(manejador.formatter, FormatoJson) for manejador in raiz.handlers):
        manejador = logging.StreamHandler(sys.stdout)
        manejador.setFormatter(FormatoJson())
        raiz.addHandler(manejador)
    raiz.setLevel(nivel.upper())
    # uvicorn trae sus propios manejadores: que todo pase por el de la raíz
    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        registro = logging.getLogger(nombre)
        registro.handlers.clear()
        registro.propagate = True
    # httpx registra la URL de cada petición, y la de la Bot API lleva el token de Telegram (§12.7)
    logging.getLogger("httpx").setLevel(logging.WARNING)
