"""add user profile completed flag

Revision ID: 0002_user_profile_completed
Revises: 0001_initial
Create Date: 2026-05-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '0002_user_profile_completed'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column['name'] for column in inspect(bind).get_columns('users')}
    if 'profile_completed' not in columns:
        op.add_column('users', sa.Column('profile_completed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('users', 'profile_completed', server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column['name'] for column in inspect(bind).get_columns('users')}
    if 'profile_completed' in columns:
        op.drop_column('users', 'profile_completed')
