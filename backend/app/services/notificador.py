"""Entrega de avisos (§10.1): a todos los miembros activos de la casa, por sus canales.

Cada aviso se entrega en una tarea aparte, con su propia sesión de base: un servicio de push
lento nunca frena la ingesta MQTT. Telegram se suma en F4b, en paralelo con Web Push.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models
from app.services.avisos import Aviso
from app.services.webpush import MAX_FALLOS, CanalWebPush, Destino, Resultado

log = logging.getLogger(__name__)


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class Notificador:
    def __init__(
        self,
        sesiones: async_sessionmaker[AsyncSession],
        webpush: CanalWebPush,
        reloj: Callable[[], datetime] = ahora_utc,
    ) -> None:
        self.sesiones = sesiones
        self.webpush = webpush
        self.reloj = reloj
        self._tareas: set[asyncio.Task[None]] = set()

    def avisar(self, aviso: Aviso, *, usuario_id: int | None = None) -> None:
        """Entrega el aviso en segundo plano. Con `usuario_id`, solo a ese usuario (la prueba
        del perfil); si no, a todos los miembros activos de la casa del aviso."""
        tarea = asyncio.create_task(self._entregar(aviso, usuario_id))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def esperar(self) -> None:
        """Espera las entregas en curso (pruebas y apagado de la API)."""
        while self._tareas:
            await asyncio.gather(*list(self._tareas), return_exceptions=True)

    async def _entregar(self, aviso: Aviso, usuario_id: int | None) -> None:
        try:
            async with self.sesiones() as db:
                destinos = await self._destinos(db, aviso, usuario_id)
            resultados = await self.webpush.enviar(destinos, aviso)
            async with self.sesiones() as db:
                await self._registrar(db, resultados, aviso)
                await db.commit()
        except Exception:
            log.exception("No se pudo entregar el aviso %s", aviso.tag)

    async def _destinos(
        self, db: AsyncSession, aviso: Aviso, usuario_id: int | None
    ) -> list[Destino]:
        if not self.webpush.activo:
            return []
        suscripcion, usuario = models.SuscripcionPush, models.Usuario
        consulta = (
            select(suscripcion.id, suscripcion.endpoint, suscripcion.p256dh, suscripcion.auth)
            .join(usuario, usuario.id == suscripcion.usuario_id)
            .where(usuario.activo)
            .order_by(suscripcion.id)
        )
        if usuario_id is not None:
            consulta = consulta.where(usuario.id == usuario_id)
        else:
            # Todos los miembros de la casa, sin importar el rol, que tengan Web Push activo
            consulta = consulta.join(
                models.Miembro,
                (models.Miembro.usuario_id == usuario.id)
                & (models.Miembro.casa_id == aviso.casa_id),
            ).where(usuario.notif_webpush)
        return [Destino(*fila) for fila in (await db.execute(consulta)).all()]

    async def _registrar(self, db: AsyncSession, resultados: list[Resultado], aviso: Aviso) -> None:
        """Una sola vez por ronda: el estado de cada suscripción y el conteo de la alarma (§10.1)."""
        suscripcion = models.SuscripcionPush
        por_entrega: dict[str, list[int]] = {}
        for resultado in resultados:
            por_entrega.setdefault(resultado.entrega, []).append(resultado.suscripcion_id)
        if ids := por_entrega.get("entregado"):
            await db.execute(
                update(suscripcion)
                .where(suscripcion.id.in_(ids))
                .values(ultimo_exito_en=self.reloj(), fallos_consecutivos=0)
            )
        if ids := por_entrega.get("caducada"):
            await db.execute(delete(suscripcion).where(suscripcion.id.in_(ids)))
            log.info("Se borraron %d suscripciones push que ya no existen", len(ids))
        if ids := por_entrega.get("fallo"):
            await db.execute(
                update(suscripcion)
                .where(suscripcion.id.in_(ids))
                .values(fallos_consecutivos=suscripcion.fallos_consecutivos + 1)
            )
            await db.execute(
                delete(suscripcion).where(
                    suscripcion.id.in_(ids), suscripcion.fallos_consecutivos >= MAX_FALLOS
                )
            )
        if aviso.alarma_id is not None:
            await db.execute(
                update(models.Alarma)
                .where(models.Alarma.id == aviso.alarma_id)
                .values(avisos_enviados=models.Alarma.avisos_enviados + 1)
            )
