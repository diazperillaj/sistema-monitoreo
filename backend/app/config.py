"""Configuración por variables de entorno (§5.6). docker-compose.yml las pasa desde el .env."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# En la imagen, el Dockerfile copia el build de React a /app/frontend (§5.2).
DIRECTORIO_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Base de datos: la URL la arma docker-compose.yml con los valores POSTGRES_*
    database_url: str

    # API
    entorno: Literal["produccion", "desarrollo"] = "produccion"
    dominio: str = "sistemamonitoreo.duckdns.org"
    log_level: str = "INFO"
    origen_permitido: Annotated[list[str], NoDecode] = ["https://sistemamonitoreo.duckdns.org"]
    sesion_dias: int = Field(default=30, ge=1)
    directorio_frontend: Path = DIRECTORIO_FRONTEND

    # MQTT: backend -> broker interno (§6.2)
    mqtt_host: str = "mosquitto"
    mqtt_puerto: int = 1883
    mqtt_usuario: str = "backend_api"
    mqtt_clave: str = ""

    # Web Push (§10.2) y Telegram, opcional (§10.7)
    vapid_clave_publica: str = ""
    vapid_clave_privada: str = ""
    vapid_sujeto: str = ""
    telegram_bot_token: str = ""

    # Reglas de negocio: valores por defecto para casas nuevas
    recordatorio_min_defecto: int = Field(default=5, ge=0)
    recordatorio_conexion_min_defecto: int = Field(default=60, ge=0)
    minutos_central_caida_defecto: int = Field(default=1, ge=1)
    timeout_confirmacion_comando_s: int = Field(default=8, ge=1)

    @field_validator("origen_permitido", mode="before")
    @classmethod
    def separar_por_comas(cls, valor: Any) -> Any:
        if isinstance(valor, str):
            return [origen.strip() for origen in valor.split(",") if origen.strip()]
        return valor

    @property
    def cookie_segura(self) -> bool:
        """Safari no guarda cookies Secure en http://localhost (§12.2)."""
        return self.entorno == "produccion"


@lru_cache
def obtener_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # database_url llega por el entorno
