"""user_settings: the offline cache rules, the same in every browser

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-12 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('user_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cache_unread', sa.Boolean(), nullable=False),
    sa.Column('cache_opened_unread', sa.Boolean(), nullable=False),
    sa.Column('cache_inbox', sa.Boolean(), nullable=False),
    sa.Column('cache_inbox_count', sa.Integer(), nullable=False),
    sa.Column('cache_max_age_days', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_settings'))
    )
# end def


def downgrade() -> None:
    op.drop_table('user_settings')
# end def
