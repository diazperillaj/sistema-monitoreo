"""Preferencias de notificación de cada usuario y la notificación de prueba (§8.7)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PreferenciasWebPush(BaseModel):
    activo: bool  # usuarios.notif_webpush
    dispositivos: int  # suscripciones del usuario


class PreferenciasTelegram(BaseModel):
    disponible: bool  # false: el servidor no tiene Telegram y la app oculta la sección
    bot: str | None
    vinculado: bool
    cuenta: str | None
    vinculado_en: datetime | None
    activo: bool


class Preferencias(BaseModel):
    webpush: PreferenciasWebPush
    telegram: PreferenciasTelegram


class CambioPreferencias(BaseModel):
    webpush: bool | None = None
    telegram: bool | None = None


class Prueba(BaseModel):
    canal: Literal["webpush", "telegram", "todos"]


class ResultadoPrueba(BaseModel):
    webpush: int  # dispositivos a los que se envió
    telegram: bool
