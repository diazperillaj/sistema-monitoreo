"""Invitaciones: el alta de usuarios por enlace (§8.2)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints

from app.schemas.auth import ClaveNueva
from app.schemas.comun import Rol, UsuarioBreve

NombrePersona = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class InvitacionNueva(BaseModel):
    rol: Rol
    email: EmailStr | None = None  # solo para recordar a quién se invitó


class InvitacionCreada(BaseModel):
    id: int
    url: str  # https://<DOMINIO>/invitacion/<token>: el token solo existe aquí, no en la base
    expira_en: datetime


class InvitacionVigente(BaseModel):
    id: int
    rol: Rol
    email: str | None
    creada_en: datetime
    expira_en: datetime
    creada_por: UsuarioBreve | None


class InvitacionPublica(BaseModel):
    """Lo que ve quien abre el enlace, sin sesión."""

    casa_nombre: str
    rol: Rol
    email: str | None


class AceptarInvitacion(BaseModel):
    """Sin sesión: nombre, email y clave crean la cuenta. Con sesión: el cuerpo va vacío."""

    nombre: NombrePersona | None = None
    email: EmailStr | None = None
    clave: ClaveNueva | None = None
