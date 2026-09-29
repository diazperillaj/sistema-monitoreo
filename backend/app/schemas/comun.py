"""Tipos y formato de error comunes a toda la API (§8)."""

from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel

Rol = Literal["admin", "cuidador"]


class UsuarioBreve(BaseModel):
    """Quién hizo algo: silenció una alarma, envió un comando…"""

    id: int
    nombre: str


class DetalleError(BaseModel):
    codigo: str
    mensaje: str
    campos: list[str] | None = None  # solo en solicitud_invalida: los datos que fallaron


class Error(BaseModel):
    """{"detail": {"codigo": ..., "mensaje": ...}}"""

    detail: DetalleError


DESCRIPCIONES = {
    400: "Solicitud inválida",
    401: "No autenticado",
    403: "Sin permiso u origen inválido",
    404: "No encontrado",
    409: "Conflicto",
    429: "Demasiados intentos",
    503: "Servicio no disponible",
}


def respuestas_error(*estados: int) -> dict[int | str, dict[str, Any]]:
    """Para documentar en OpenAPI los errores que puede dar un endpoint."""
    return {estado: {"model": Error, "description": DESCRIPCIONES[estado]} for estado in estados}


def error_api(
    estado: int, codigo: str, mensaje: str, cabeceras: dict[str, str] | None = None
) -> HTTPException:
    return HTTPException(estado, {"codigo": codigo, "mensaje": mensaje}, headers=cabeceras)
