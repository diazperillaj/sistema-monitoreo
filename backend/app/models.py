"""Tablas de la base de datos (§7.2), con los tipos de §7.0 y los índices de §7.3.

Las tablas de Telegram (telegram_vinculos, codigos_telegram) y usuarios.notif_telegram
llegan con su propia migración en F4b.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Los mismos nombres que pondría PostgreSQL: migraciones estables y fáciles de leer
CONVENCION_NOMBRES = {
    "pk": "%(table_name)s_pkey",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "ix": "%(table_name)s_%(column_0_name)s_idx",
}

ROLES = ("admin", "cuidador")
TIPOS_ALARMA = (
    "INTRUSION",
    "SIN_MOVIMIENTO",
    "AGUA",
    "GAS",
    "TEMPERATURA",
    "NODO_SIN_CONEXION",
    "CENTRAL_DESCONECTADA",
)
CERRADA_POR = ("usuario", "central", "automatica")
ORIGENES_EVENTO = ("central", "backend", "usuario")
TIPOS_EVENTO = ("alarma", "alarma_resuelta", "comando", "habilitado", "conexion", "central", "info")
ACCIONES = ("activar", "desactivar", "silenciar")
ESTADOS_COMANDO = ("pendiente", "confirmado", "sin_confirmar")
METRICAS = ("temperatura", "gas", "caudal")


def en(columna: str, valores: tuple[str, ...]) -> str:
    """El texto de un CHECK (columna IN (...)): así se guardan las enumeraciones (§7.0)."""
    return f"{columna} IN ({', '.join(repr(valor) for valor in valores)})"


def clave_primaria() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


def momento_actual() -> Mapped[datetime]:
    """TIMESTAMPTZ NOT NULL con default now()."""
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def referencia(tabla: str, al_borrar: str, **opciones: Any) -> Mapped[Any]:
    return mapped_column(BigInteger, ForeignKey(f"{tabla}.id", ondelete=al_borrar), **opciones)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email"),)

    id: Mapped[int] = clave_primaria()
    email: Mapped[str] = mapped_column(Text, unique=True)
    nombre: Mapped[str] = mapped_column(Text)
    clave_hash: Mapped[str] = mapped_column(Text)  # Argon2id
    es_superadmin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    notif_webpush: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    creado_en: Mapped[datetime] = momento_actual()
    ultimo_login_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Sesion(Base):
    __tablename__ = "sesiones"
    __table_args__ = (
        Index("sesiones_usuario", "usuario_id"),
        Index("sesiones_expira", "expira_en"),
    )

    id: Mapped[int] = clave_primaria()
    usuario_id: Mapped[int] = referencia("usuarios", "CASCADE")
    token_hash: Mapped[str] = mapped_column(Text, unique=True)  # sha256 del token, en hex
    creada_en: Mapped[datetime] = momento_actual()
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ultimo_uso_en: Mapped[datetime] = momento_actual()
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)


class Casa(Base):
    __tablename__ = "casas"
    __table_args__ = (
        CheckConstraint("codigo ~ '^[a-z0-9-]{4,40}$'", name="codigo"),
        CheckConstraint("recordatorio_min >= 0", name="recordatorio_min"),
        CheckConstraint("recordatorio_conexion_min >= 0", name="recordatorio_conexion_min"),
        CheckConstraint("minutos_central_caida >= 1", name="minutos_central_caida"),
    )

    id: Mapped[int] = clave_primaria()
    codigo: Mapped[str] = mapped_column(Text, unique=True)  # = ID_CASA = usuario MQTT de la central
    nombre: Mapped[str] = mapped_column(Text)
    recordatorio_min: Mapped[int] = mapped_column(Integer, default=5, server_default=text("5"))
    recordatorio_conexion_min: Mapped[int] = mapped_column(
        Integer, default=60, server_default=text("60")
    )
    minutos_central_caida: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    avisar_nodo_sin_conexion: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    avisar_resueltas: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    creada_en: Mapped[datetime] = momento_actual()


class Miembro(Base):
    __tablename__ = "miembros"
    __table_args__ = (CheckConstraint(en("rol", ROLES), name="rol"),)

    usuario_id: Mapped[int] = referencia(
        "usuarios", "CASCADE", primary_key=True, autoincrement=False
    )
    casa_id: Mapped[int] = referencia("casas", "CASCADE", primary_key=True, autoincrement=False)
    rol: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = momento_actual()


class Invitacion(Base):
    __tablename__ = "invitaciones"
    __table_args__ = (CheckConstraint(en("rol", ROLES), name="rol"),)

    id: Mapped[int] = clave_primaria()
    casa_id: Mapped[int] = referencia("casas", "CASCADE")
    email: Mapped[str | None] = mapped_column(Text)  # solo informativo
    rol: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    creada_por: Mapped[int | None] = referencia("usuarios", "SET NULL")
    creada_en: Mapped[datetime] = momento_actual()
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # 72 h
    usada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usada_por: Mapped[int | None] = referencia("usuarios", "SET NULL")


class EstadoActual(Base):
    """Una fila por casa (§7.2): se escribe con INSERT ... ON CONFLICT en cada estado."""

    __tablename__ = "estado_actual"

    casa_id: Mapped[int] = referencia("casas", "CASCADE", primary_key=True, autoincrement=False)
    online: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    online_cambio_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    recibido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Alarma(Base):
    __tablename__ = "alarmas"
    __table_args__ = (
        CheckConstraint("nodo_id BETWEEN 0 AND 4", name="nodo_id"),
        CheckConstraint(en("tipo", TIPOS_ALARMA), name="tipo"),
        CheckConstraint(en("cerrada_por", CERRADA_POR), name="cerrada_por"),
        # Una sola alarma abierta por (casa, nodo, tipo). NULLS NOT DISTINCT hace que
        # CENTRAL_DESCONECTADA (nodo_id NULL) también sea única (§7.3).
        Index(
            "alarmas_una_abierta",
            "casa_id",
            "nodo_id",
            "tipo",
            unique=True,
            postgresql_where=text("fin_en IS NULL"),
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = clave_primaria()
    casa_id: Mapped[int] = referencia("casas", "CASCADE")
    nodo_id: Mapped[int | None] = mapped_column(SmallInteger)  # NULL en CENTRAL_DESCONECTADA
    tipo: Mapped[str] = mapped_column(Text)
    inicio_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NULL = abierta
    valor: Mapped[float | None] = mapped_column(Double)
    limite_s: Mapped[int | None] = mapped_column(Integer)
    cerrada_por: Mapped[str | None] = mapped_column(Text)
    cerrada_por_usuario_id: Mapped[int | None] = referencia("usuarios", "SET NULL")
    avisos_enviados: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    ultimo_aviso_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Evento(Base):
    __tablename__ = "eventos"
    __table_args__ = (
        CheckConstraint(en("origen", ORIGENES_EVENTO), name="origen"),
        CheckConstraint(en("tipo", TIPOS_EVENTO), name="tipo"),
    )

    id: Mapped[int] = clave_primaria()
    casa_id: Mapped[int] = referencia("casas", "CASCADE")
    ocurrido_en: Mapped[datetime] = momento_actual()  # eventos de la central: momento de recepción
    origen: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = referencia("usuarios", "SET NULL")
    nodo_id: Mapped[int | None] = mapped_column(SmallInteger)
    tipo: Mapped[str] = mapped_column(Text)
    texto: Mapped[str] = mapped_column(Text)
    es_alarma: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class Comando(Base):
    __tablename__ = "comandos"
    __table_args__ = (
        CheckConstraint(en("accion", ACCIONES), name="accion"),
        CheckConstraint("sub IN (0, 1)", name="sub"),
        CheckConstraint(en("estado", ESTADOS_COMANDO), name="estado"),
        Index(
            "comandos_pendientes",
            "casa_id",
            "creado_en",
            postgresql_where=text("estado = 'pendiente'"),
        ),
    )

    id: Mapped[int] = clave_primaria()
    casa_id: Mapped[int] = referencia("casas", "CASCADE")
    usuario_id: Mapped[int | None] = referencia("usuarios", "SET NULL")
    nodo_id: Mapped[int | None] = mapped_column(SmallInteger)  # NULL = todo
    accion: Mapped[str] = mapped_column(Text)
    sub: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))
    payload: Mapped[str] = mapped_column(Text)  # lo que se publicó en casa/<ID>/cmd
    estado: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = momento_actual()
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SuscripcionPush(Base):
    __tablename__ = "suscripciones_push"
    __table_args__ = (Index("suscripciones_usuario", "usuario_id"),)

    id: Mapped[int] = clave_primaria()
    usuario_id: Mapped[int] = referencia("usuarios", "CASCADE")
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    creada_en: Mapped[datetime] = momento_actual()
    ultimo_exito_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fallos_consecutivos: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class Lectura(Base):
    """Series para las gráficas, una muestra por minuto (§7.2)."""

    __tablename__ = "lecturas"
    __table_args__ = (
        CheckConstraint(en("metrica", METRICAS), name="metrica"),
        Index("lecturas_fecha", "medido_en"),  # para la limpieza por retención
    )

    casa_id: Mapped[int] = referencia("casas", "CASCADE", primary_key=True, autoincrement=False)
    nodo_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    metrica: Mapped[str] = mapped_column(Text, primary_key=True)
    medido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    valor: Mapped[float] = mapped_column(Double)


Index("alarmas_casa_inicio", Alarma.casa_id, Alarma.inicio_en.desc())
Index("eventos_casa_fecha", Evento.casa_id, Evento.ocurrido_en.desc(), Evento.id.desc())
