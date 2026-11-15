"""Eventos: la bitácora de cada casa (§8.5)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app import models
from app.schemas.comun import UsuarioBreve


class Evento(BaseModel):
    id: int
    ocurrido_en: datetime
    origen: Literal["central", "backend", "usuario"]
    usuario: UsuarioBreve | None
    nodo_id: int | None
    tipo: Literal[
        "alarma", "alarma_resuelta", "comando", "habilitado", "conexion", "central", "info"
    ]
    texto: str
    es_alarma: bool


class PaginaEventos(BaseModel):
    items: list[Evento]
    siguiente: int | None  # antes_de_id para la página siguiente; null si no hay más


def evento_a_esquema(evento: models.Evento, nombre_usuario: str | None) -> Evento:
    return Evento(
        id=evento.id,
        ocurrido_en=evento.ocurrido_en,
        origen=evento.origen,  # type: ignore[arg-type]
        usuario=(
            UsuarioBreve(id=evento.usuario_id, nombre=nombre_usuario)
            if evento.usuario_id is not None and nombre_usuario is not None
            else None
        ),
        nodo_id=evento.nodo_id,
        tipo=evento.tipo,  # type: ignore[arg-type]
        texto=evento.texto,
        es_alarma=evento.es_alarma,
    )
