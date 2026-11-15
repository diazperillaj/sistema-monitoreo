"""Web Push: la clave pública y las suscripciones de cada dispositivo (§8.7)."""

from pydantic import BaseModel, Field, field_validator

from app.services.webpush import es_servicio_push

BASE64URL = r"^[A-Za-z0-9_-]+={0,2}$"


class ClavePublica(BaseModel):
    clave: str  # applicationServerKey para pushManager.subscribe()


class ClavesPush(BaseModel):
    p256dh: str = Field(min_length=80, max_length=100, pattern=BASE64URL)
    auth: str = Field(min_length=16, max_length=32, pattern=BASE64URL)


class NuevaSuscripcion(BaseModel):
    """Lo que entrega PushSubscription.toJSON() en el navegador."""

    endpoint: str = Field(max_length=1000)
    keys: ClavesPush

    @field_validator("endpoint")
    @classmethod
    def de_un_servicio_de_push(cls, endpoint: str) -> str:
        if not es_servicio_push(endpoint):
            raise ValueError("no es la dirección de un servicio de push de un navegador")
        return endpoint


class BajaSuscripcion(BaseModel):
    endpoint: str = Field(max_length=1000)
