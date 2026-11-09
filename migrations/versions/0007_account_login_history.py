"""accounts: login history (when the credentials changed, failed logins, the last success)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-09 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('auth_failed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('auth_fail_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('auth_ok_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('auth_last_error', sa.Text(), nullable=True))
    op.execute('UPDATE accounts SET auth_updated_at = updated_at')
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.alter_column('auth_updated_at', existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column('auth_fail_count', existing_type=sa.Integer(), server_default=None)
# end def


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('auth_last_error')
        batch_op.drop_column('auth_ok_at')
        batch_op.drop_column('auth_fail_count')
        batch_op.drop_column('auth_failed_at')
        batch_op.drop_column('auth_updated_at')
# end def
