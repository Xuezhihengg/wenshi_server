"""add feedback starred

Revision ID: 0004_feedback_starred
Revises: 0003_feedback
Create Date: 2026-05-04
"""
import sqlalchemy as sa
from alembic import op

revision = '0004_feedback_starred'
down_revision = '0003_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('feedback', sa.Column('starred', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(op.f('ix_feedback_starred'), 'feedback', ['starred'], unique=False)
    op.alter_column('feedback', 'starred', server_default=None)


def downgrade() -> None:
    op.drop_index(op.f('ix_feedback_starred'), table_name='feedback')
    op.drop_column('feedback', 'starred')
