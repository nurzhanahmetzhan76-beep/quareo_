"""add autoreply tables

Revision ID: a1b2c3d4e5f6
Revises: 9b48dcb6eddd
Create Date: 2026-07-20 18:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6a141c49172'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create autoreply_settings and autoreply_history tables."""
    op.create_table(
        'autoreply_settings',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('tone', sa.String(length=32), nullable=False, server_default='friendly'),
        sa.Column('auto_send', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('language', sa.String(length=8), nullable=False, server_default='ru'),
        sa.Column('store_description', sa.Text(), nullable=False, server_default=''),
        sa.Column('custom_instructions', sa.Text(), nullable=False, server_default=''),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_autoreply_settings_user_id'), 'autoreply_settings', ['user_id'], unique=True)

    op.create_table(
        'autoreply_history',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('product_name', sa.String(length=512), nullable=True),
        sa.Column('question_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_autoreply_history_user_id'), 'autoreply_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_autoreply_history_created_at'), 'autoreply_history', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop autoreply tables."""
    op.drop_index(op.f('ix_autoreply_history_created_at'), table_name='autoreply_history')
    op.drop_index(op.f('ix_autoreply_history_user_id'), table_name='autoreply_history')
    op.drop_table('autoreply_history')
    op.drop_index(op.f('ix_autoreply_settings_user_id'), table_name='autoreply_settings')
    op.drop_table('autoreply_settings')
