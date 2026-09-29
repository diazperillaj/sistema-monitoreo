from typing import Literal

from pydantic import BaseModel


class Salud(BaseModel):
    ok: bool  # false solo si falla la base de datos (§8.8)
    db: Literal["ok", "error"]
    mqtt: Literal["conectado", "desconectado"]
    telegram: Literal["conectado", "desactivado", "error"]
    version: str
