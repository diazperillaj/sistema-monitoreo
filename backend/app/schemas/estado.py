"""Estado actual de una casa (§8.3): lo que pinta el tablero y lo que va por WebSocket."""

from datetime import datetime

from pydantic import BaseModel

from app.protocolo import EstadoCentral
from app.schemas.alarmas import Alarma


class EstadoCasa(BaseModel):
    casa_id: int
    online: bool
    online_cambio_en: datetime | None
    recibido_en: datetime | None  # último estado en vivo
    antiguedad_s: int | None  # segundos desde recibido_en
    central: EstadoCentral | None  # el payload de §4.3, con sus mismos campos y nombres
    alarmas_abiertas: list[Alarma]
