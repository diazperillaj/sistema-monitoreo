"""Aplica lo que llega de las centrales (§6.3): alarmas, eventos, estado, lecturas y WebSocket.

Cada mensaje se aplica en una sola transacción. Los avisos por WebSocket salen después del
commit: quien consulte el historial al recibirlos ya encuentra los datos guardados.
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Row, and_, exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models
from app.protocolo import EstadoCentral, EventoCentral, nombre_nodo, parsear_estado, texto_alarma
from app.schemas.alarmas import alarma_a_esquema
from app.schemas.comandos import comando_a_esquema
from app.schemas.eventos import evento_a_esquema
from app.services import comandos
from app.services.comandos import Resueltos
from app.services.detector import Abiertas, Transicion, detectar
from app.services.estado_cache import CasaEnMemoria, EstadoCache, estado_de_casa
from app.services.eventos_central import eventos_nuevos, se_importa
from app.services.lecturas import INTERVALO_S, lecturas_de
from app.services.ws_hub import HubWs

log = logging.getLogger(__name__)
ZONA = ZoneInfo("America/Bogota")  # la hora que se muestra (§3.4)
VENTANA_COMANDO = timedelta(seconds=15)  # un comando así de reciente explica el cambio (§6.4)
CENTRAL = "CENTRAL_DESCONECTADA"


def ahora_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class Cambios:
    """Lo que dejó un mensaje, para avisarlo por WebSocket después del commit."""

    central: dict[str, Any] | None = None  # {"online": ..., "cambio_en": ...}
    alarmas: list[tuple[str, models.Alarma, str | None]] = field(default_factory=list)
    eventos: list[tuple[models.Evento, str | None]] = field(default_factory=list)
    comandos: Resueltos = field(default_factory=list)


class Procesador:
    """Lo usan la ingesta MQTT y el vigilante de centrales. Un candado los pone en fila: así
    un "1" de la central no se cruza con el vigilante que está abriendo CENTRAL_DESCONECTADA."""

    def __init__(
        self,
        sesiones: async_sessionmaker[AsyncSession],
        hub: HubWs,
        cache: EstadoCache,
        reloj: Callable[[], datetime] = ahora_utc,
        cronometro: Callable[[], float] = time.monotonic,
    ) -> None:
        self.sesiones = sesiones
        self.hub = hub
        self.cache = cache
        self.reloj = reloj
        self.cronometro = cronometro
        self._candado = asyncio.Lock()
        self._desconocidas: set[str] = set()

    # ----------------------------------------------------------- casa/<codigo>/estado
    async def recibir_estado(self, codigo: str, carga: bytes, retenido: bool = False) -> None:
        try:
            nuevo = parsear_estado(carga)
            crudo = json.loads(carga)
        except ValueError as error:
            primera_linea = str(error).splitlines()[0]
            log.warning("Estado inválido de %s, descartado: %s", codigo, primera_linea)
            return
        async with self._candado:
            ahora = self.reloj()
            cambios = Cambios()
            async with self.sesiones() as db:
                casa = await self._casa(db, codigo)
                if casa is None:
                    return
                abiertas = await self._abiertas(db, casa.casa_id)
                if not retenido:
                    # Solo una central conectada publica en vivo: si la base dice lo
                    # contrario (se perdió o llegó tarde un "1"), se corrige aquí.
                    await self._en_linea(db, casa.casa_id, ahora, cambios, abiertas)
                for transicion in detectar(casa.previo, nuevo, abiertas):
                    await self._aplicar(db, casa.casa_id, transicion, ahora, cambios)
                if not retenido:  # un retenido no prueba que la central aplicó nada
                    cambios.comandos += await comandos.confirmar(db, casa.casa_id, nuevo, ahora)
                anteriores = casa.previo.eventos if casa.previo else None
                self._importar_eventos(db, casa.casa_id, anteriores, nuevo, ahora, cambios)
                await self._guardar_estado(db, casa.casa_id, crudo, ahora, retenido)
                muestrear = not retenido and self._toca_muestrear(casa)
                if muestrear:
                    await self._muestrear(db, casa.casa_id, nuevo, ahora)
                await db.commit()
            casa.previo = nuevo
            if muestrear:
                casa.ultimo_muestreo = self.cronometro()
            await self._avisar(casa.casa_id, cambios, ahora, con_estado=True)

    # ----------------------------------------------------------- casa/<codigo>/online
    async def recibir_online(self, codigo: str, carga: bytes, retenido: bool = False) -> None:
        valor = carga.decode("utf-8", errors="replace").strip()
        if valor not in ("0", "1"):
            log.warning("Valor de online inválido de %s: %r", codigo, valor[:20])
            return
        async with self._candado:
            ahora = self.reloj()
            cambios = Cambios()
            async with self.sesiones() as db:
                casa = await self._casa(db, codigo)
                if casa is None:
                    return
                if valor == "1":
                    await self._en_linea(db, casa.casa_id, ahora, cambios)
                else:
                    await self._fuera_de_linea(db, casa.casa_id, ahora, cambios)
                await db.commit()
            await self._avisar(casa.casa_id, cambios, ahora, con_estado=False)

    # ----------------------------------------------------------- vigilante_central (§6.2)
    async def revisar_centrales_caidas(self) -> None:
        """Abre CENTRAL_DESCONECTADA en las casas con la central caída más de
        minutos_central_caida. La alarma empieza cuando se cayó la central."""
        estado, alarma = models.EstadoActual, models.Alarma
        async with self._candado:
            ahora = self.reloj()
            avisos: list[tuple[int, Cambios]] = []
            async with self.sesiones() as db:
                caidas = await db.execute(
                    select(
                        estado.casa_id, estado.online_cambio_en, models.Casa.minutos_central_caida
                    )
                    .join(models.Casa, models.Casa.id == estado.casa_id)
                    .where(
                        estado.online.is_(False),
                        estado.online_cambio_en.is_not(None),
                        ~exists().where(
                            alarma.casa_id == estado.casa_id,
                            alarma.tipo == CENTRAL,
                            alarma.fin_en.is_(None),
                        ),
                    )
                )
                for casa_id, desde, minutos in caidas.all():
                    if ahora - desde < timedelta(minutes=minutos):
                        continue  # una caída corta no alcanza a ser alarma
                    cambios = Cambios()
                    nueva = await self._abrir(db, casa_id, None, CENTRAL, desde)
                    if nueva is not None:
                        cambios.alarmas.append(("abre", nueva, None))
                        hora = desde.astimezone(ZONA).strftime("%H:%M")
                        texto = f"Central desconectada desde las {hora}"
                        self._evento(db, casa_id, ahora, cambios, "alarma", texto, es_alarma=True)
                        avisos.append((casa_id, cambios))
                await db.commit()
            for casa_id, cambios in avisos:
                await self._avisar(casa_id, cambios, ahora, con_estado=False)

    # ----------------------------------------------------------- comandos_timeout (§6.2)
    async def vencer_comandos(self, timeout_s: float) -> None:
        """Marca sin_confirmar los comandos que la central no confirmó a tiempo (§6.5)."""
        async with self._candado:
            ahora = self.reloj()
            por_casa: dict[int, Cambios] = {}
            async with self.sesiones() as db:
                limite = ahora - timedelta(seconds=timeout_s)
                for comando, nombre in await comandos.vencer(db, limite, ahora):
                    cambios = por_casa.setdefault(comando.casa_id, Cambios())
                    cambios.comandos.append((comando, nombre))
                    texto = comandos.texto_sin_confirmar(
                        nombre, comando.accion, comando.nodo_id, comando.sub
                    )
                    self._evento(
                        db,
                        comando.casa_id,
                        ahora,
                        cambios,
                        "comando",
                        texto,
                        nodo_id=comando.nodo_id,
                        usuario_id=comando.usuario_id,
                        usuario=nombre,
                    )
                if por_casa:
                    await db.commit()
            for casa_id, cambios in por_casa.items():
                await self._avisar(casa_id, cambios, ahora, con_estado=False)

    # ----------------------------------------------------------- transiciones del detector
    async def _aplicar(
        self, db: AsyncSession, casa_id: int, t: Transicion, ahora: datetime, cambios: Cambios
    ) -> None:
        nodo = nombre_nodo(t.nodo_id)
        if t.tipo == "alarma_abre" and t.tipo_alarma:
            alarma = await self._abrir(
                db, casa_id, t.nodo_id, t.tipo_alarma, ahora, valor=t.valor, limite_s=t.limite_s
            )
            if alarma is not None:
                cambios.alarmas.append(("abre", alarma, None))
                texto = f"{nodo}: {texto_alarma(alarma.tipo, alarma.limite_s, alarma.valor)}"
                self._evento(
                    db, casa_id, ahora, cambios, "alarma", texto, nodo_id=t.nodo_id, es_alarma=True
                )
        elif t.tipo == "alarma_cierra" and t.tipo_alarma:
            comando = await self._comando_que_cierra(db, casa_id, t.nodo_id, ahora)
            usuario_id = comando.usuario_id if comando else None
            usuario = comando.nombre if comando else None
            por = "usuario" if comando else "central"
            alarma = await self._cerrar(
                db, casa_id, t.nodo_id, t.tipo_alarma, ahora, por, usuario_id
            )
            if alarma is not None:
                cambios.alarmas.append(("cierra", alarma, usuario))
                if comando is None:
                    detalle = "se normalizó"  # botón BOOT, app local o fin natural
                else:
                    hecho = "silenciada" if comando.accion == "silenciar" else "desactivada"
                    detalle = f"{hecho} por {usuario}" if usuario else f"{hecho} desde la app"
                texto = f"{nodo}: {texto_alarma(alarma.tipo, alarma.limite_s, alarma.valor)}"
                self._evento(
                    db,
                    casa_id,
                    ahora,
                    cambios,
                    "alarma_resuelta",
                    f"{texto} · {detalle}",
                    nodo_id=t.nodo_id,
                    usuario_id=usuario_id,
                    usuario=usuario,
                )
        elif t.tipo == "nodo_offline":
            desde = ahora - timedelta(seconds=t.hace_s)  # cuando dejó de reportar
            alarma = await self._abrir(db, casa_id, t.nodo_id, "NODO_SIN_CONEXION", desde)
            if alarma is not None:
                cambios.alarmas.append(("abre", alarma, None))
                texto = f"{nodo} perdió la conexión"
                self._evento(
                    db,
                    casa_id,
                    ahora,
                    cambios,
                    "conexion",
                    texto,
                    nodo_id=t.nodo_id,
                    es_alarma=True,
                )
        elif t.tipo == "nodo_online":
            alarma = await self._cerrar(
                db, casa_id, t.nodo_id, "NODO_SIN_CONEXION", ahora, "automatica"
            )
            if alarma is not None:
                cambios.alarmas.append(("cierra", alarma, None))
                texto = f"{nodo} volvió a conectarse"
                self._evento(db, casa_id, ahora, cambios, "conexion", texto, nodo_id=t.nodo_id)
        elif t.tipo == "habilitado_cambia" and t.por_horario:
            acciones = ("activar", "desactivar")
            if not await self._hubo_comando(db, casa_id, t.nodo_id, acciones, ahora):
                texto = f"{nodo} {'activada' if t.hab_nuevo else 'desactivada'} (horario)"
                self._evento(db, casa_id, ahora, cambios, "habilitado", texto, nodo_id=t.nodo_id)

    # ----------------------------------------------------------- conexión de la central
    async def _en_linea(
        self,
        db: AsyncSession,
        casa_id: int,
        ahora: datetime,
        cambios: Cambios,
        abiertas: Abiertas | None = None,
    ) -> None:
        fila = await db.get(models.EstadoActual, casa_id)
        estaba_caida = fila is None or not fila.online
        if fila is None:
            db.add(models.EstadoActual(casa_id=casa_id, online=True, online_cambio_en=ahora))
        elif estaba_caida:
            fila.online, fila.online_cambio_en = True, ahora
        cerrada = None
        if abiertas is None or (None, CENTRAL) in abiertas:
            cerrada = await self._cerrar(db, casa_id, None, CENTRAL, ahora, "automatica")
            if cerrada is not None:
                cambios.alarmas.append(("cierra", cerrada, None))
        if estaba_caida or cerrada is not None:
            texto = "La central volvió a conectarse" if cerrada else "La central se conectó"
            self._evento(db, casa_id, ahora, cambios, "central", texto)
            cambios.central = {"online": True, "cambio_en": ahora.isoformat()}

    async def _fuera_de_linea(
        self, db: AsyncSession, casa_id: int, ahora: datetime, cambios: Cambios
    ) -> None:
        fila = await db.get(models.EstadoActual, casa_id)
        if fila is not None and not fila.online and fila.online_cambio_en is not None:
            return  # ya estaba así (por ejemplo, el "0" retenido tras reiniciar el backend)
        # Sin online_cambio_en la conexión era desconocida: la fila la creó un estado retenido.
        # Desde ahora cuenta la caída; si no, el vigilante nunca abriría CENTRAL_DESCONECTADA.
        if fila is None:
            db.add(models.EstadoActual(casa_id=casa_id, online=False, online_cambio_en=ahora))
        else:
            fila.online, fila.online_cambio_en = False, ahora
        self._evento(db, casa_id, ahora, cambios, "central", "La central se desconectó")
        cambios.central = {"online": False, "cambio_en": ahora.isoformat()}

    # ----------------------------------------------------------- base de datos
    async def _casa(self, db: AsyncSession, codigo: str) -> CasaEnMemoria | None:
        casa = await self.cache.casa(db, codigo)
        if casa is None and codigo not in self._desconocidas:
            self._desconocidas.add(codigo)
            log.warning("Llegan mensajes de la central %s, pero esa casa no existe", codigo)
        return casa

    @staticmethod
    async def _abiertas(db: AsyncSession, casa_id: int) -> Abiertas:
        filas = await db.execute(
            select(models.Alarma.nodo_id, models.Alarma.tipo).where(
                models.Alarma.casa_id == casa_id, models.Alarma.fin_en.is_(None)
            )
        )
        return {(nodo_id, tipo) for nodo_id, tipo in filas.all()}

    @staticmethod
    async def _abrir(
        db: AsyncSession,
        casa_id: int,
        nodo_id: int | None,
        tipo: str,
        inicio: datetime,
        valor: float | None = None,
        limite_s: int | None = None,
    ) -> models.Alarma | None:
        """INSERT ... ON CONFLICT DO NOTHING RETURNING (§7.3): si ya estaba abierta (por
        ejemplo, por un mensaje MQTT duplicado) no devuelve nada y no se avisa dos veces."""
        sentencia = (
            insert(models.Alarma)
            .values(
                casa_id=casa_id,
                nodo_id=nodo_id,
                tipo=tipo,
                inicio_en=inicio,
                valor=valor,
                limite_s=limite_s,
            )
            .on_conflict_do_nothing(
                index_elements=["casa_id", "nodo_id", "tipo"],
                index_where=models.Alarma.fin_en.is_(None),
            )
            .returning(models.Alarma)
        )
        return (await db.execute(sentencia)).scalar_one_or_none()

    @staticmethod
    async def _cerrar(
        db: AsyncSession,
        casa_id: int,
        nodo_id: int | None,
        tipo: str,
        fin: datetime,
        cerrada_por: str,
        usuario_id: int | None = None,
    ) -> models.Alarma | None:
        sentencia = (
            update(models.Alarma)
            .where(
                models.Alarma.casa_id == casa_id,
                models.Alarma.nodo_id.is_not_distinct_from(nodo_id),
                models.Alarma.tipo == tipo,
                models.Alarma.fin_en.is_(None),
            )
            .values(fin_en=fin, cerrada_por=cerrada_por, cerrada_por_usuario_id=usuario_id)
            .returning(models.Alarma)
        )
        return (await db.execute(sentencia)).scalar_one_or_none()

    @staticmethod
    async def _comando_que_cierra(
        db: AsyncSession, casa_id: int, nodo_id: int, ahora: datetime
    ) -> Row[int | None, str, str | None] | None:
        """El silenciar o desactivar de ese nodo, o el todo:silenciar, de los últimos 15 s (§6.4)."""
        comando = models.Comando
        return (
            await db.execute(
                select(comando.usuario_id, comando.accion, models.Usuario.nombre)
                .outerjoin(models.Usuario, models.Usuario.id == comando.usuario_id)
                .where(
                    comando.casa_id == casa_id,
                    comando.creado_en >= ahora - VENTANA_COMANDO,
                    or_(
                        and_(
                            comando.nodo_id == nodo_id,
                            comando.accion.in_(("silenciar", "desactivar")),
                        ),
                        and_(comando.nodo_id.is_(None), comando.accion == "silenciar"),
                    ),
                )
                .order_by(comando.creado_en.desc(), comando.id.desc())
                .limit(1)
            )
        ).first()

    @staticmethod
    async def _hubo_comando(
        db: AsyncSession, casa_id: int, nodo_id: int, acciones: tuple[str, ...], ahora: datetime
    ) -> bool:
        return bool(
            await db.scalar(
                select(
                    exists().where(
                        models.Comando.casa_id == casa_id,
                        models.Comando.nodo_id == nodo_id,
                        models.Comando.accion.in_(acciones),
                        models.Comando.creado_en >= ahora - VENTANA_COMANDO,
                    )
                )
            )
        )

    @staticmethod
    def _evento(
        db: AsyncSession,
        casa_id: int,
        ahora: datetime,
        cambios: Cambios,
        tipo: str,
        texto: str,
        *,
        nodo_id: int | None = None,
        usuario_id: int | None = None,
        usuario: str | None = None,
        es_alarma: bool = False,
        origen: str = "backend",
    ) -> None:
        evento = models.Evento(
            casa_id=casa_id,
            ocurrido_en=ahora,
            origen=origen,
            tipo=tipo,
            texto=texto,
            nodo_id=nodo_id,
            usuario_id=usuario_id,
            es_alarma=es_alarma,
        )
        db.add(evento)
        cambios.eventos.append((evento, usuario))

    def _importar_eventos(
        self,
        db: AsyncSession,
        casa_id: int,
        anteriores: Sequence[EventoCentral] | None,
        nuevo: EstadoCentral,
        ahora: datetime,
        cambios: Cambios,
    ) -> None:
        # Del más antiguo al más reciente: así los ids siguen el orden en que ocurrieron
        for evento in reversed(eventos_nuevos(anteriores, nuevo.eventos)):
            if se_importa(evento):
                self._evento(
                    db,
                    casa_id,
                    ahora,
                    cambios,
                    "central",
                    evento.x,
                    es_alarma=evento.a,
                    origen="central",
                )

    @staticmethod
    async def _guardar_estado(
        db: AsyncSession, casa_id: int, crudo: dict[str, Any], ahora: datetime, retenido: bool
    ) -> None:
        valores: dict[str, Any] = {"casa_id": casa_id, "payload": crudo}
        if not retenido:  # un retenido puede tener horas: no cuenta como dato reciente (§6.3)
            valores["recibido_en"] = ahora
        sentencia = insert(models.EstadoActual).values(**valores)
        await db.execute(
            sentencia.on_conflict_do_update(
                index_elements=["casa_id"],
                set_={
                    columna: sentencia.excluded[columna]
                    for columna in valores
                    if columna != "casa_id"
                },
            )
        )

    def _toca_muestrear(self, casa: CasaEnMemoria) -> bool:
        return (
            casa.ultimo_muestreo is None or self.cronometro() - casa.ultimo_muestreo >= INTERVALO_S
        )

    @staticmethod
    async def _muestrear(
        db: AsyncSession, casa_id: int, estado: EstadoCentral, ahora: datetime
    ) -> None:
        filas = [
            {
                "casa_id": casa_id,
                "nodo_id": nodo,
                "metrica": metrica,
                "medido_en": ahora,
                "valor": valor,
            }
            for nodo, metrica, valor in lecturas_de(estado)
        ]
        if filas:
            await db.execute(insert(models.Lectura).values(filas).on_conflict_do_nothing())

    # ----------------------------------------------------------- WebSocket (§9)
    async def _avisar(
        self, casa_id: int, cambios: Cambios, ahora: datetime, *, con_estado: bool
    ) -> None:
        if not self.hub.hay_clientes(casa_id):
            return
        if cambios.central is not None:
            await self.hub.emitir(casa_id, {"tipo": "central", **cambios.central})
        for accion, alarma, usuario in cambios.alarmas:
            datos = alarma_a_esquema(alarma, ahora, usuario).model_dump(mode="json")
            await self.hub.emitir(casa_id, {"tipo": "alarma", "evento": accion, "data": datos})
        for evento, usuario in cambios.eventos:
            datos = evento_a_esquema(evento, usuario).model_dump(mode="json")
            await self.hub.emitir(casa_id, {"tipo": "evento", "data": datos})
        for comando, usuario in cambios.comandos:
            datos = comando_a_esquema(comando, usuario).model_dump(mode="json")
            await self.hub.emitir(casa_id, {"tipo": "comando", "data": datos})
        if con_estado:
            async with self.sesiones() as db:
                estado = await estado_de_casa(db, casa_id, ahora)
            datos = estado.model_dump(mode="json", by_alias=True)
            await self.hub.emitir(casa_id, {"tipo": "estado", "data": datos})
