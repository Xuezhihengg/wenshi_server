"""add user profile completed flag

Revision ID: 0002_user_profile_completed
Revises: 0001_initial
Create Date: 2026-05-04
"""
import sqlalchemy as sa
from alembic import op

revision = '0002_user_profile_completed'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('profile_completed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('users', 'profile_completed', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'profile_completed')
