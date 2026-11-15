"""Cambios de membresía: quién entra, cambia de rol o sale de una casa. Quedan en el historial."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.schemas.eventos import evento_a_esquema
from app.services.auth import ahora
from app.services.ws_hub import HubWs


def texto_union(persona: str, rol: str) -> str:
    return f"{persona} se unió a la casa como {rol}"


def texto_rol(actor: str, persona: str, rol: str) -> str:
    if rol == "admin":
        return f"{actor} hizo admin a {persona}"
    return f"{actor} dejó a {persona} como cuidador"


def texto_salida(actor: str, persona: str, misma_persona: bool) -> str:
    return (
        f"{persona} salió de la casa" if misma_persona else f"{actor} quitó a {persona} de la casa"
    )


def nuevo_evento(casa_id: int, usuario_id: int, texto: str) -> models.Evento:
    """El evento de un cambio de membresía (sin commit: va en la misma transacción del cambio)."""
    return models.Evento(
        casa_id=casa_id,
        ocurrido_en=ahora(),
        origen="usuario",
        usuario_id=usuario_id,
        tipo="info",
        texto=texto,
        es_alarma=False,
    )


async def avisar(hub: HubWs, evento: models.Evento, nombre_usuario: str) -> None:
    """Después del commit: el historial abierto en otros celulares se actualiza (§9)."""
    await hub.emitir(
        evento.casa_id,
        {
            "tipo": "evento",
            "data": evento_a_esquema(evento, nombre_usuario).model_dump(mode="json"),
        },
    )


async def contar_admins(db: AsyncSession, casa_id: int) -> int:
    consulta = (
        select(func.count())
        .select_from(models.Miembro)
        .where(models.Miembro.casa_id == casa_id, models.Miembro.rol == "admin")
    )
    return await db.scalar(consulta) or 0
