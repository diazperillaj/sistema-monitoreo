"""Miembros de una casa (§8.6)."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.comun import Rol


class PersonaMiembro(BaseModel):
    id: int
    nombre: str
    email: str


class MiembroCasa(BaseModel):
    usuario: PersonaMiembro
    rol: Rol
    creado_en: datetime


class CambioMiembro(BaseModel):
    rol: Rol
