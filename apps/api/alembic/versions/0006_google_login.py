"""add google login

Revision ID: 0006_google_login
Revises: 0005_portal_visits
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = '0006_google_login'
down_revision = '0005_portal_visits'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE authprovider ADD VALUE IF NOT EXISTS 'google'")
    op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=False)
    op.create_unique_constraint('uq_users_google_id', 'users', ['google_id'])


def downgrade() -> None:
    op.drop_constraint('uq_users_google_id', 'users', type_='unique')
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_column('users', 'google_id')
