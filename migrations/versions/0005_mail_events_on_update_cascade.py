"""mail_events: the account id follows a changed accounts.id (ON UPDATE CASCADE)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04 12:00:00.000000
"""

from alembic import op


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

FK = 'fk_mail_events_account_id_accounts'


def upgrade() -> None:
    with op.batch_alter_table('mail_events', schema=None) as batch_op:
        batch_op.drop_constraint(FK, type_='foreignkey')
        batch_op.create_foreign_key(FK, 'accounts', ['account_id'], ['id'], ondelete='CASCADE', onupdate='CASCADE')
# end def


def downgrade() -> None:
    with op.batch_alter_table('mail_events', schema=None) as batch_op:
        batch_op.drop_constraint(FK, type_='foreignkey')
        batch_op.create_foreign_key(FK, 'accounts', ['account_id'], ['id'], ondelete='CASCADE')
# end def
