"""Casas y sus ajustes (§8.3)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.comun import Rol

CodigoCasa = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{4,40}$")]  # = ID_CASA
NombreCasa = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Minutos = Annotated[int, Field(ge=0, le=1440)]  # 0 = sin recordatorios
MinutosCaida = Annotated[int, Field(ge=1, le=1440)]


class Ajustes(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recordatorio_min: Minutos
    recordatorio_conexion_min: Minutos
    minutos_central_caida: MinutosCaida
    avisar_nodo_sin_conexion: bool
    avisar_resueltas: bool


class CambioAjustes(BaseModel):
    """Solo cambian los campos que se envían."""

    recordatorio_min: Minutos | None = None
    recordatorio_conexion_min: Minutos | None = None
    minutos_central_caida: MinutosCaida | None = None
    avisar_nodo_sin_conexion: bool | None = None
    avisar_resueltas: bool | None = None


class Casa(BaseModel):
    id: int
    codigo: str
    nombre: str
    creada_en: datetime
    ajustes: Ajustes


class ResumenCasa(BaseModel):
    id: int
    codigo: str
    nombre: str
    rol: Rol  # el superadmin figura como admin en las casas de las que no es miembro
    online: bool
    alarmas_abiertas: int


class CasaNueva(BaseModel):
    codigo: CodigoCasa
    nombre: NombreCasa


class CambioCasa(BaseModel):
    nombre: NombreCasa | None = None
