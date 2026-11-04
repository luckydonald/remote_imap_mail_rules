"""git_settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-04 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('git_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('auto_commit', sa.Boolean(), nullable=False),
    sa.Column('auto_push', sa.Boolean(), nullable=False),
    sa.Column('remote_url', sa.String(length=1024), nullable=False),
    sa.Column('branch', sa.String(length=255), nullable=False),
    sa.Column('auth_method', sa.String(length=16), nullable=False),
    sa.Column('username', sa.String(length=255), nullable=False),
    sa.Column('token_encrypted', sa.Text(), nullable=False),
    sa.Column('author_name', sa.String(length=255), nullable=False),
    sa.Column('author_email', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_git_settings'))
    )
# end def


def downgrade() -> None:
    op.drop_table('git_settings')
# end def
