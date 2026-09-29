"""Autenticación y sesiones (§8.1)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.comun import Rol

ClaveNueva = Annotated[str, Field(min_length=10, max_length=128)]  # mínimo 10 caracteres (§12.1)


class Login(BaseModel):
    email: EmailStr
    clave: str = Field(min_length=1, max_length=128)


class Usuario(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    es_superadmin: bool


class CasaDelUsuario(BaseModel):
    id: int
    nombre: str
    rol: Rol


class Yo(BaseModel):
    usuario: Usuario
    casas: list[CasaDelUsuario]


class CambioClave(BaseModel):
    clave_actual: str = Field(min_length=1, max_length=128)
    clave_nueva: ClaveNueva


class SesionAbierta(BaseModel):
    id: int
    user_agent: str | None
    ip: str | None
    creada_en: datetime
    ultimo_uso_en: datetime
    expira_en: datetime
    actual: bool  # la sesión desde la que se hace la consulta
