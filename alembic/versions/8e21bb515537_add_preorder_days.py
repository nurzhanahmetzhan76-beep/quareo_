"""Add preorder_days

Revision ID: 8e21bb515537
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24 10:55:21.452648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e21bb515537'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('repricing_rules', sa.Column('preorder_days', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repricing_rules', 'preorder_days')
