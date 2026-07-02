"""Initial model

Revision ID: 6b19178641a7
Revises: 
Create Date: 2026-06-02 20:52:50.384315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6b19178641a7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables: products, niche_analyses, pools, pool_participants."""

    # ── Products ──────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kaspi_id", sa.String(64), nullable=False, unique=True, index=True,
                  comment="Kaspi internal product ID"),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("category_slug", sa.String(128), nullable=False, index=True,
                  comment="Category slug, e.g. air-humidifiers"),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("photo_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_infographics", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("description_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seller_name", sa.String(256), nullable=True),
        sa.Column("seller_count", sa.Integer(), nullable=False, server_default="0",
                  comment="Number of sellers offering this product"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ── Niche Analyses ────────────────────────────────────────────────
    op.create_table(
        "niche_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_slug", sa.String(128), nullable=False, index=True),
        sa.Column("demand_score", sa.Float(), nullable=False, server_default="0.0",
                  comment="Proxy for demand (e.g. review volume, search rank)"),
        sa.Column("seller_count_in_category", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monopolization_index", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("visual_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_vulnerable", sa.Boolean(), nullable=False, server_default="false",
                  index=True,
                  comment="True if >50% of top-10 cards in the category are weak"),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ── Pool status enum type ─────────────────────────────────────────
    pool_status_enum = postgresql.ENUM(
        "open", "closed", "completed", "expired", "cancelled",
        name="pool_status", create_type=True,
    )
    pool_status_enum.create(op.get_bind(), checkfirst=True)

    # ── Pools ─────────────────────────────────────────────────────────
    op.create_table(
        "pools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("target_quantity", sa.Integer(), nullable=False,
                  comment="Minimum total units required for wholesale order"),
        sa.Column("target_amount", sa.Float(), nullable=False,
                  comment="Minimum total amount (KZT) to qualify for wholesale pricing"),
        sa.Column("current_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", pool_status_enum, nullable=False, server_default="open",
                  index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False,
                  comment="Deadline for reaching quorum"),
    )

    # ── Pool Participants ─────────────────────────────────────────────
    op.create_table(
        "pool_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pool_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pools.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True,
                  comment="External user identifier"),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False,
                  comment="Individual contribution (KZT)"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table("pool_participants")
    op.drop_table("pools")

    # Drop the enum type
    pool_status_enum = postgresql.ENUM(
        "open", "closed", "completed", "expired", "cancelled",
        name="pool_status",
    )
    pool_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_table("niche_analyses")
    op.drop_table("products")
