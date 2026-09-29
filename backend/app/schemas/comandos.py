"""Comandos a la central (§8.4): silenciar, activar y desactivar."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app import models
from app.protocolo import Accion, sub_valido
from app.schemas.comun import UsuarioBreve


class ComandoNuevo(BaseModel):
    nodo: int = Field(ge=0, le=4)
    accion: Accion
    sub: Literal[0, 1] = Field(
        default=0, description="1 = presencia del nodo 4; solo para activar o desactivar"
    )

    @model_validator(mode="after")
    def sub_solo_en_la_presencia(self) -> Self:
        if not sub_valido(self.nodo, self.accion, self.sub):
            raise ValueError("sub = 1 solo existe en el nodo 4, para activar o desactivar")
        return self


class Comando(BaseModel):
    id: int
    nodo_id: int | None  # null = todo:silenciar
    accion: Accion
    sub: int
    estado: Literal["pendiente", "confirmado", "sin_confirmar"]
    creado_en: datetime
    resuelto_en: datetime | None  # al confirmarse o vencer
    usuario: UsuarioBreve | None  # quien lo envió; null si ya no existe


def comando_a_esquema(comando: models.Comando, nombre_usuario: str | None) -> Comando:
    return Comando(
        id=comando.id,
        nodo_id=comando.nodo_id,
        accion=comando.accion,  # type: ignore[arg-type]
        sub=comando.sub,
        estado=comando.estado,  # type: ignore[arg-type]
        creado_en=comando.creado_en,
        resuelto_en=comando.resuelto_en,
        usuario=(
            UsuarioBreve(id=comando.usuario_id, nombre=nombre_usuario)
            if comando.usuario_id is not None and nombre_usuario is not None
            else None
        ),
    )
