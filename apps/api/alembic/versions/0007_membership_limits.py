"""add membership quota usage events

Revision ID: 0007_membership_limits
Revises: 0006_google_login
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0007_membership_limits'
down_revision = '0006_google_login'
branch_labels = None
depends_on = None


def _uuid_type() -> sa.types.TypeEngine:
    bind = op.get_context().bind
    if bind and bind.dialect.name == 'postgresql':
        return postgresql.UUID(as_uuid=False)
    return sa.String(length=36)


def _membership_plan_type() -> sa.types.TypeEngine:
    bind = op.get_context().bind
    if bind and bind.dialect.name == 'postgresql':
        return postgresql.ENUM('trial', 'monthly', 'yearly', name='membershipplan', create_type=False)
    return sa.String(length=32)


def upgrade() -> None:
    op.create_table(
        'ai_reading_usage_events',
        sa.Column('user_id', _uuid_type(), nullable=False),
        sa.Column('record_id', _uuid_type(), nullable=True),
        sa.Column('plan', _membership_plan_type(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lang', sa.String(length=8), nullable=False, server_default='zh'),
        sa.Column('id', _uuid_type(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['record_id'], ['fortune_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_reading_usage_events_record_id'), 'ai_reading_usage_events', ['record_id'], unique=False)
    op.create_index(op.f('ix_ai_reading_usage_events_used_at'), 'ai_reading_usage_events', ['used_at'], unique=False)
    op.create_index(op.f('ix_ai_reading_usage_events_user_id'), 'ai_reading_usage_events', ['user_id'], unique=False)
    op.create_index('ix_ai_usage_user_used_at', 'ai_reading_usage_events', ['user_id', 'used_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ai_usage_user_used_at', table_name='ai_reading_usage_events')
    op.drop_index(op.f('ix_ai_reading_usage_events_user_id'), table_name='ai_reading_usage_events')
    op.drop_index(op.f('ix_ai_reading_usage_events_used_at'), table_name='ai_reading_usage_events')
    op.drop_index(op.f('ix_ai_reading_usage_events_record_id'), table_name='ai_reading_usage_events')
    op.drop_table('ai_reading_usage_events')
