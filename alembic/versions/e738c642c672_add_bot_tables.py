"""add bot tables

Revision ID: e738c642c672
Revises: 72cc7211946b
Create Date: 2026-07-11 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'e738c642c672'
down_revision: Union[str, Sequence[str], None] = '72cc7211946b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    # Add telegram_id to users
    columns = [c["name"] for c in inspector.get_columns("users")]
    if "telegram_id" not in columns:
        op.add_column('users', sa.Column('telegram_id', sa.BigInteger(), nullable=True))
        op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    
    if "user_seller_settings" not in tables:
        op.create_table('user_seller_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('kaspi_api_key', sa.Text(), nullable=True),
        sa.Column('kaspi_merchant_id', sa.String(length=128), nullable=True),
        sa.Column('kaspi_shop_name', sa.String(length=256), nullable=True),
        sa.Column('nkt_api_key', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_user_seller_settings_user_id'), 'user_seller_settings', ['user_id'], unique=True)
        
    if "repricing_rules" not in tables:
        op.create_table('repricing_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('kaspi_sku', sa.String(length=128), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('product_url', sa.Text(), nullable=True),
        sa.Column('min_price', sa.Float(), nullable=False),
        sa.Column('base_price', sa.Float(), nullable=True),
        sa.Column('step_kzt', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('my_current_price', sa.Float(), nullable=False),
        sa.Column('last_competitor_price', sa.Float(), nullable=True),
        sa.Column('my_merchant_name', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_repricing_rules_user_id'), 'repricing_rules', ['user_id'], unique=False)
        
    if "repricing_logs" not in tables:
        op.create_table('repricing_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('rule_id', sa.Uuid(), nullable=False),
        sa.Column('old_price', sa.Float(), nullable=False),
        sa.Column('new_price', sa.Float(), nullable=False),
        sa.Column('competitor_price', sa.Float(), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['repricing_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_repricing_logs_rule_id'), 'repricing_logs', ['rule_id'], unique=False)


def downgrade() -> None:
    pass
