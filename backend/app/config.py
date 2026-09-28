"""Configuración por variables de entorno (§5.6). docker-compose.yml las pasa desde el .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# En la imagen, el Dockerfile copia el build de React a /app/frontend (§5.2).
DIRECTORIO_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    entorno: Literal["produccion", "desarrollo"] = "produccion"
    dominio: str = "sistemamonitoreo.duckdns.org"
    log_level: str = "INFO"
    database_url: str | None = None  # la arma docker-compose.yml; db.py la exige desde F1
    directorio_frontend: Path = DIRECTORIO_FRONTEND


@lru_cache
def obtener_settings() -> Settings:
    return Settings()
