"""user_settings: auto_read, when the mail view marks a mail read by itself

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-13 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('user_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auto_read', sa.String(length=16), server_default='off', nullable=False))
# end def


def downgrade() -> None:
    with op.batch_alter_table('user_settings', schema=None) as batch_op:
        batch_op.drop_column('auto_read')
# end def
