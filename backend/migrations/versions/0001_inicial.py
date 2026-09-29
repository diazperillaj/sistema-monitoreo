"""Esquema inicial (§7.2 y §7.3): todas las tablas salvo las de Telegram, que llegan en F4b.

Revisada a mano: índices parciales (alarmas_una_abierta con NULLS NOT DISTINCT y
comandos_pendientes) e índices descendentes (alarmas_casa_inicio y eventos_casa_fecha).

Revision ID: 0001
Revises:
Create Date: 2026-09-28 19:40:25.816669
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "casas",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("recordatorio_min", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column(
            "recordatorio_conexion_min", sa.Integer(), server_default=sa.text("60"), nullable=False
        ),
        sa.Column(
            "minutos_central_caida", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "avisar_nodo_sin_conexion", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("avisar_resueltas", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("codigo ~ '^[a-z0-9-]{4,40}$'", name=op.f("casas_codigo_check")),
        sa.CheckConstraint(
            "minutos_central_caida >= 1", name=op.f("casas_minutos_central_caida_check")
        ),
        sa.CheckConstraint(
            "recordatorio_conexion_min >= 0", name=op.f("casas_recordatorio_conexion_min_check")
        ),
        sa.CheckConstraint("recordatorio_min >= 0", name=op.f("casas_recordatorio_min_check")),
        sa.PrimaryKeyConstraint("id", name=op.f("casas_pkey")),
        sa.UniqueConstraint("codigo", name=op.f("casas_codigo_key")),
    )
    op.create_table(
        "usuarios",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("clave_hash", sa.Text(), nullable=False),
        sa.Column("es_superadmin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notif_webpush", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("ultimo_login_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("email = lower(email)", name=op.f("usuarios_email_check")),
        sa.PrimaryKeyConstraint("id", name=op.f("usuarios_pkey")),
        sa.UniqueConstraint("email", name=op.f("usuarios_email_key")),
    )
    op.create_table(
        "alarmas",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("casa_id", sa.BigInteger(), nullable=False),
        sa.Column("nodo_id", sa.SmallInteger(), nullable=True),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("inicio_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valor", sa.Double(), nullable=True),
        sa.Column("limite_s", sa.Integer(), nullable=True),
        sa.Column("cerrada_por", sa.Text(), nullable=True),
        sa.Column("cerrada_por_usuario_id", sa.BigInteger(), nullable=True),
        sa.Column("avisos_enviados", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ultimo_aviso_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "cerrada_por IN ('usuario', 'central', 'automatica')",
            name=op.f("alarmas_cerrada_por_check"),
        ),
        sa.CheckConstraint(
            "tipo IN ('INTRUSION', 'SIN_MOVIMIENTO', 'AGUA', 'GAS', 'TEMPERATURA', 'NODO_SIN_CONEXION', 'CENTRAL_DESCONECTADA')",
            name=op.f("alarmas_tipo_check"),
        ),
        sa.CheckConstraint("nodo_id BETWEEN 0 AND 4", name=op.f("alarmas_nodo_id_check")),
        sa.ForeignKeyConstraint(
            ["casa_id"], ["casas.id"], name=op.f("alarmas_casa_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cerrada_por_usuario_id"],
            ["usuarios.id"],
            name=op.f("alarmas_cerrada_por_usuario_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("alarmas_pkey")),
    )
    op.create_index(
        "alarmas_casa_inicio",
        "alarmas",
        ["casa_id", sa.literal_column("inicio_en DESC")],
        unique=False,
    )
    op.create_index(
        "alarmas_una_abierta",
        "alarmas",
        ["casa_id", "nodo_id", "tipo"],
        unique=True,
        postgresql_where=sa.text("fin_en IS NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_table(
        "comandos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("casa_id", sa.BigInteger(), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=True),
        sa.Column("nodo_id", sa.SmallInteger(), nullable=True),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("sub", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "accion IN ('activar', 'desactivar', 'silenciar')", name=op.f("comandos_accion_check")
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'confirmado', 'sin_confirmar')",
            name=op.f("comandos_estado_check"),
        ),
        sa.CheckConstraint("sub IN (0, 1)", name=op.f("comandos_sub_check")),
        sa.ForeignKeyConstraint(
            ["casa_id"], ["casas.id"], name=op.f("comandos_casa_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("comandos_usuario_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("comandos_pkey")),
    )
    op.create_index(
        "comandos_pendientes",
        "comandos",
        ["casa_id", "creado_en"],
        unique=False,
        postgresql_where=sa.text("estado = 'pendiente'"),
    )
    op.create_table(
        "estado_actual",
        sa.Column("casa_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("online", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("online_cambio_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["casa_id"], ["casas.id"], name=op.f("estado_actual_casa_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("casa_id", name=op.f("estado_actual_pkey")),
    )
    op.create_table(
        "eventos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("casa_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "ocurrido_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("origen", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=True),
        sa.Column("nodo_id", sa.SmallInteger(), nullable=True),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("es_alarma", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "origen IN ('central', 'backend', 'usuario')", name=op.f("eventos_origen_check")
        ),
        sa.CheckConstraint(
            "tipo IN ('alarma', 'alarma_resuelta', 'comando', 'habilitado', 'conexion', 'central', 'info')",
            name=op.f("eventos_tipo_check"),
        ),
        sa.ForeignKeyConstraint(
            ["casa_id"], ["casas.id"], name=op.f("eventos_casa_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("eventos_usuario_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("eventos_pkey")),
    )
    op.create_index(
        "eventos_casa_fecha",
        "eventos",
        ["casa_id", sa.literal_column("ocurrido_en DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_table(
        "invitaciones",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("casa_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("rol", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("creada_por", sa.BigInteger(), nullable=True),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usada_por", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("rol IN ('admin', 'cuidador')", name=op.f("invitaciones_rol_check")),
        sa.ForeignKeyConstraint(
            ["casa_id"], ["casas.id"], name=op.f("invitaciones_casa_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["creada_por"],
            ["usuarios.id"],
            name=op.f("invitaciones_creada_por_fkey"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["usada_por"],
            ["usuarios.id"],
            name=op.f("invitaciones_usada_por_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("invitaciones_pkey")),
        sa.UniqueConstraint("token_hash", name=op.f("invitaciones_token_hash_key")),
    )
    op.create_table(
        "lecturas",
        sa.Column("casa_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("nodo_id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("metrica", sa.Text(), nullable=False),
        sa.Column("medido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valor", sa.Double(), nullable=False),
        sa.CheckConstraint(
            "metrica IN ('temperatura', 'gas', 'caudal')", name=op.f("lecturas_metrica_check")
        ),
        sa.ForeignKeyConstraint(
            ["casa_id"], ["casas.id"], name=op.f("lecturas_casa_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint(
            "casa_id", "nodo_id", "metrica", "medido_en", name=op.f("lecturas_pkey")
        ),
    )
    op.create_index("lecturas_fecha", "lecturas", ["medido_en"], unique=False)
    op.create_table(
        "miembros",
        sa.Column("usuario_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("casa_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("rol", sa.Text(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("rol IN ('admin', 'cuidador')", name=op.f("miembros_rol_check")),
        sa.ForeignKeyConstraint(
            ["casa_id"], ["casas.id"], name=op.f("miembros_casa_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("miembros_usuario_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "casa_id", name=op.f("miembros_pkey")),
    )
    op.create_table(
        "sesiones",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ultimo_uso_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("sesiones_usuario_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("sesiones_pkey")),
        sa.UniqueConstraint("token_hash", name=op.f("sesiones_token_hash_key")),
    )
    op.create_index("sesiones_expira", "sesiones", ["expira_en"], unique=False)
    op.create_index("sesiones_usuario", "sesiones", ["usuario_id"], unique=False)
    op.create_table(
        "suscripciones_push",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("ultimo_exito_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fallos_consecutivos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("suscripciones_push_usuario_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("suscripciones_push_pkey")),
        sa.UniqueConstraint("endpoint", name=op.f("suscripciones_push_endpoint_key")),
    )
    op.create_index("suscripciones_usuario", "suscripciones_push", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index("suscripciones_usuario", table_name="suscripciones_push")
    op.drop_table("suscripciones_push")
    op.drop_index("sesiones_usuario", table_name="sesiones")
    op.drop_index("sesiones_expira", table_name="sesiones")
    op.drop_table("sesiones")
    op.drop_table("miembros")
    op.drop_index("lecturas_fecha", table_name="lecturas")
    op.drop_table("lecturas")
    op.drop_table("invitaciones")
    op.drop_index("eventos_casa_fecha", table_name="eventos")
    op.drop_table("eventos")
    op.drop_table("estado_actual")
    op.drop_index(
        "comandos_pendientes",
        table_name="comandos",
        postgresql_where=sa.text("estado = 'pendiente'"),
    )
    op.drop_table("comandos")
    op.drop_index(
        "alarmas_una_abierta",
        table_name="alarmas",
        postgresql_where=sa.text("fin_en IS NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.drop_index("alarmas_casa_inicio", table_name="alarmas")
    op.drop_table("alarmas")
    op.drop_table("usuarios")
    op.drop_table("casas")
