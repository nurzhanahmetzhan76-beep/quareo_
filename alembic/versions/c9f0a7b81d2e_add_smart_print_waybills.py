"""add Smart Print waybill tracking

Revision ID: c9f0a7b81d2e
Revises: 8e21bb515537
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c9f0a7b81d2e"
down_revision: Union[str, Sequence[str], None] = "8e21bb515537"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "processed_waybills" not in inspector.get_table_names():
        op.create_table(
            "processed_waybills",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("waybill_id", sa.String(length=256), nullable=False),
            sa.Column("store_name", sa.String(length=256), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "waybill_id", name="uq_processed_waybill_user_id"),
        )
        op.create_index("ix_processed_waybills_user_id", "processed_waybills", ["user_id"], unique=False)
        op.create_index("ix_processed_waybills_processed_at", "processed_waybills", ["processed_at"], unique=False)

    if "waybill_upload_history" not in inspector.get_table_names():
        op.create_table(
            "waybill_upload_history",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("total_count", sa.Integer(), nullable=False),
            sa.Column("already_processed_count", sa.Integer(), nullable=False),
            sa.Column("new_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_waybill_upload_history_user_id", "waybill_upload_history", ["user_id"], unique=False)
        op.create_index("ix_waybill_upload_history_created_at", "waybill_upload_history", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_waybill_upload_history_created_at", table_name="waybill_upload_history")
    op.drop_index("ix_waybill_upload_history_user_id", table_name="waybill_upload_history")
    op.drop_table("waybill_upload_history")
    op.drop_index("ix_processed_waybills_processed_at", table_name="processed_waybills")
    op.drop_index("ix_processed_waybills_user_id", table_name="processed_waybills")
    op.drop_table("processed_waybills")
