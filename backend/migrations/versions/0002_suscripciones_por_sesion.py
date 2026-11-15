"""Suscripciones push atadas a la sesión y notificaciones por casa (§7.2, §10.1, S17).

- suscripciones_push.sesion_id (FK a sesiones, ON DELETE CASCADE): al salir de la cuenta, al
  cerrar la sesión o al vencer, el dispositivo deja de recibir. Las suscripciones que ya
  existían no tienen sesión y se borran: la app las vuelve a registrar sola la próxima vez que
  se abra con la sesión iniciada (si el navegador sigue suscrito).
- casas.notificaciones_activas: interruptor general de los avisos de la casa.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM suscripciones_push")
    op.add_column("suscripciones_push", sa.Column("sesion_id", sa.BigInteger(), nullable=False))
    op.create_foreign_key(
        op.f("suscripciones_push_sesion_id_fkey"),
        "suscripciones_push",
        "sesiones",
        ["sesion_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("suscripciones_sesion", "suscripciones_push", ["sesion_id"], unique=False)
    op.add_column(
        "casas",
        sa.Column(
            "notificaciones_activas", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("casas", "notificaciones_activas")
    op.drop_index("suscripciones_sesion", table_name="suscripciones_push")
    op.drop_constraint(
        op.f("suscripciones_push_sesion_id_fkey"), "suscripciones_push", type_="foreignkey"
    )
    op.drop_column("suscripciones_push", "sesion_id")
