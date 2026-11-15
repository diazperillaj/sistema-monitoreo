"""Lecturas para las gráficas y resumen de alarmas (§8.5)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Metrica = Literal["temperatura", "gas", "caudal"]
Agregacion = Literal["1m", "5m", "1h"]


class Punto(BaseModel):
    t: datetime  # inicio del intervalo
    valor: float  # promedio en el intervalo


class AlarmasDelDia(BaseModel):
    dia: date  # en la hora de Bogotá
    sensor: int  # intrusión, sin movimiento, agua, gas y temperatura
    conexion: int  # nodo sin conexión y central desconectada


class Resumen(BaseModel):
    dias: int
    alarmas_por_tipo: dict[str, int]
    tiempo_medio_respuesta_s: float | None  # de las que silenció alguien desde la app o Telegram
    alarmas_por_dia: list[AlarmasDelDia]  # un elemento por día, también los días sin alarmas
