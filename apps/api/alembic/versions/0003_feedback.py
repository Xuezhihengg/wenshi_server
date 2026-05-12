"""add feedback

Revision ID: 0003_feedback
Revises: 0002_user_profile_completed
Create Date: 2026-05-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0003_feedback'
down_revision = '0002_user_profile_completed'
branch_labels = None
depends_on = None


def _uuid_type():
    return postgresql.UUID(as_uuid=False)


def upgrade() -> None:
    feedback_type = postgresql.ENUM('bug', 'feature', 'experience', 'other', name='feedbacktype', create_type=False)
    feedback_status = postgresql.ENUM('open', 'reviewing', 'resolved', 'ignored', name='feedbackstatus', create_type=False)
    feedback_type.create(op.get_bind(), checkfirst=True)
    feedback_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'feedback',
        sa.Column('user_id', _uuid_type(), nullable=False),
        sa.Column('type', feedback_type, nullable=False),
        sa.Column('status', feedback_status, nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('screenshot_urls', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('app_version', sa.String(length=80), nullable=True),
        sa.Column('platform', sa.String(length=40), nullable=True),
        sa.Column('device_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', _uuid_type(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_feedback_status'), 'feedback', ['status'], unique=False)
    op.create_index(op.f('ix_feedback_type'), 'feedback', ['type'], unique=False)
    op.create_index(op.f('ix_feedback_user_id'), 'feedback', ['user_id'], unique=False)
    op.create_index('ix_feedback_created_at', 'feedback', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_feedback_created_at', table_name='feedback')
    op.drop_index(op.f('ix_feedback_user_id'), table_name='feedback')
    op.drop_index(op.f('ix_feedback_type'), table_name='feedback')
    op.drop_index(op.f('ix_feedback_status'), table_name='feedback')
    op.drop_table('feedback')
    postgresql.ENUM(name='feedbackstatus').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='feedbacktype').drop(op.get_bind(), checkfirst=True)
