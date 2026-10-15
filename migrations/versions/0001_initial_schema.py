"""Начальная схема: тарифы и платежи

Revision ID: 0001
Revises:
Create Date: 2026-10-15

Денежные колонки — BigInteger (копейки). График рассрочки — JSON-массив
целых чисел. Уникальный индекс по idempotency_key держит повторы.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tariffs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tariff_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("discount", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("installment_months", sa.Integer(), nullable=True),
        sa.Column("schedule", sa.JSON(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tariff_id"], ["tariffs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_payments_email"), ["email"], unique=False)
        batch_op.create_index(batch_op.f("ix_payments_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_payments_tariff_id"), ["tariff_id"], unique=False)
        batch_op.create_index("ix_payments_email_status", ["email", "status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_index("ix_payments_email_status")
        batch_op.drop_index(batch_op.f("ix_payments_tariff_id"))
        batch_op.drop_index(batch_op.f("ix_payments_status"))
        batch_op.drop_index(batch_op.f("ix_payments_email"))

    op.drop_table("payments")
    op.drop_table("tariffs")
