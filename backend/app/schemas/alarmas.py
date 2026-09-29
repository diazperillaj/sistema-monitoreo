"""Alarmas: los incidentes de cada casa (§8.5)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app import models
from app.protocolo import TipoAlarma, nombre_nodo, texto_alarma
from app.schemas.comun import UsuarioBreve


class Alarma(BaseModel):
    id: int
    nodo_id: int | None  # null en CENTRAL_DESCONECTADA
    nodo_nombre: str
    tipo: TipoAlarma
    texto: str
    inicio_en: datetime
    fin_en: datetime | None  # null = abierta
    duracion_s: int
    valor: float | None
    cerrada_por: Literal["usuario", "central", "automatica"] | None
    cerrada_por_usuario: UsuarioBreve | None
    avisos_enviados: int


class PaginaAlarmas(BaseModel):
    items: list[Alarma]
    siguiente: int | None  # antes_de_id para la página siguiente; null si no hay más


def alarma_a_esquema(alarma: models.Alarma, ahora: datetime, nombre_usuario: str | None) -> Alarma:
    fin = alarma.fin_en or ahora
    return Alarma(
        id=alarma.id,
        nodo_id=alarma.nodo_id,
        nodo_nombre=nombre_nodo(alarma.nodo_id),
        tipo=alarma.tipo,  # type: ignore[arg-type]
        texto=texto_alarma(alarma.tipo, alarma.limite_s, alarma.valor),
        inicio_en=alarma.inicio_en,
        fin_en=alarma.fin_en,
        duracion_s=max(0, int((fin - alarma.inicio_en).total_seconds())),
        valor=alarma.valor,
        cerrada_por=alarma.cerrada_por,  # type: ignore[arg-type]
        cerrada_por_usuario=(
            UsuarioBreve(id=alarma.cerrada_por_usuario_id, nombre=nombre_usuario)
            if alarma.cerrada_por_usuario_id is not None and nombre_usuario is not None
            else None
        ),
        avisos_enviados=alarma.avisos_enviados,
    )
