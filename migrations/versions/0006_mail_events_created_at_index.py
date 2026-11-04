"""mail_events: an index on created_at for the cross-account action log screen

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04 13:00:00.000000
"""

from alembic import op


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

INDEX = 'ix_mail_events_created_at'


def upgrade() -> None:
    with op.batch_alter_table('mail_events', schema=None) as batch_op:
        batch_op.create_index(INDEX, ['created_at'], unique=False)
# end def


def downgrade() -> None:
    with op.batch_alter_table('mail_events', schema=None) as batch_op:
        batch_op.drop_index(INDEX)
# end def
