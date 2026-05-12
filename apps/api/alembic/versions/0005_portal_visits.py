"""add portal visits

Revision ID: 0005_portal_visits
Revises: 0004_feedback_starred
Create Date: 2026-05-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0005_portal_visits'
down_revision = '0004_feedback_starred'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'portal_visits',
        sa.Column('path', sa.String(length=255), nullable=False),
        sa.Column('language', sa.String(length=12), nullable=True),
        sa.Column('referrer', sa.Text(), nullable=True),
        sa.Column('utm_source', sa.String(length=120), nullable=True),
        sa.Column('utm_medium', sa.String(length=120), nullable=True),
        sa.Column('utm_campaign', sa.String(length=160), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('session_id', sa.String(length=80), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portal_visits_ip_hash'), 'portal_visits', ['ip_hash'], unique=False)
    op.create_index(op.f('ix_portal_visits_language'), 'portal_visits', ['language'], unique=False)
    op.create_index(op.f('ix_portal_visits_path'), 'portal_visits', ['path'], unique=False)
    op.create_index(op.f('ix_portal_visits_session_id'), 'portal_visits', ['session_id'], unique=False)
    op.create_index(op.f('ix_portal_visits_utm_campaign'), 'portal_visits', ['utm_campaign'], unique=False)
    op.create_index(op.f('ix_portal_visits_utm_medium'), 'portal_visits', ['utm_medium'], unique=False)
    op.create_index(op.f('ix_portal_visits_utm_source'), 'portal_visits', ['utm_source'], unique=False)
    op.create_index('ix_portal_visits_created_path', 'portal_visits', ['created_at', 'path'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_portal_visits_created_path', table_name='portal_visits')
    op.drop_index(op.f('ix_portal_visits_utm_source'), table_name='portal_visits')
    op.drop_index(op.f('ix_portal_visits_utm_medium'), table_name='portal_visits')
    op.drop_index(op.f('ix_portal_visits_utm_campaign'), table_name='portal_visits')
    op.drop_index(op.f('ix_portal_visits_session_id'), table_name='portal_visits')
    op.drop_index(op.f('ix_portal_visits_path'), table_name='portal_visits')
    op.drop_index(op.f('ix_portal_visits_language'), table_name='portal_visits')
    op.drop_index(op.f('ix_portal_visits_ip_hash'), table_name='portal_visits')
    op.drop_table('portal_visits')
