"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def _uuid_type():
    return postgresql.UUID(as_uuid=False)


def _json_type():
    return postgresql.JSONB(astext_type=sa.Text())


def _enum_type(name: str, *values: str):
    return postgresql.ENUM(*values, name=name, create_type=False)


def _create_pg_enums(*enums) -> None:
    bind = op.get_bind()
    for enum in enums:
        enum.create(bind, checkfirst=True)


def _drop_pg_enums(*names: str) -> None:
    bind = op.get_bind()
    for name in names:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)


def timestamps_and_id():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', _uuid_type(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    ]


def upgrade() -> None:
    auth_provider = _enum_type('authprovider', 'phone', 'email', 'apple', 'wechat')
    membership_plan = _enum_type('membershipplan', 'trial', 'monthly', 'yearly')
    membership_status = _enum_type('membershipstatus', 'trial', 'active', 'expired', 'cancelled')
    order_channel = _enum_type('orderchannel', 'apple', 'wechat', 'alipay', 'mock')
    order_status = _enum_type('orderstatus', 'pending', 'paid', 'failed', 'cancelled')
    verification_purpose = _enum_type('verificationpurpose', 'login', 'bind')
    _create_pg_enums(auth_provider, membership_plan, membership_status, order_channel, order_status, verification_purpose)

    op.create_table(
        'users',
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('apple_id', sa.String(length=255), nullable=True),
        sa.Column('wechat_id', sa.String(length=255), nullable=True),
        sa.Column('display_name', sa.String(length=80), nullable=False),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('register_provider', auth_provider, nullable=False),
        sa.Column('membership_plan', membership_plan, nullable=False),
        sa.Column('membership_status', membership_status, nullable=False),
        sa.Column('membership_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('profile_completed', sa.Boolean(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('disabled', sa.Boolean(), nullable=False),
        *timestamps_and_id(),
        sa.UniqueConstraint('apple_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('wechat_id'),
    )
    op.create_index(op.f('ix_users_apple_id'), 'users', ['apple_id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=False)
    op.create_index(op.f('ix_users_wechat_id'), 'users', ['wechat_id'], unique=False)

    op.create_table(
        'profiles',
        sa.Column('user_id', _uuid_type(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('relation', sa.String(length=40), nullable=False),
        sa.Column('gender', sa.String(length=20), nullable=False),
        sa.Column('birthday', sa.String(length=120), nullable=False),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('is_selected', sa.Boolean(), nullable=False),
        *timestamps_and_id(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_profiles_user_id'), 'profiles', ['user_id'], unique=False)
    op.create_index('ix_profiles_user_selected', 'profiles', ['user_id', 'is_selected'], unique=False)

    op.create_table(
        'fortune_records',
        sa.Column('user_id', _uuid_type(), nullable=False),
        sa.Column('profile_id', _uuid_type(), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('hexagram_name', sa.String(length=80), nullable=True),
        sa.Column('changed_hexagram_name', sa.String(length=80), nullable=True),
        sa.Column('favorite', sa.Boolean(), nullable=False),
        sa.Column('cast_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', _json_type(), nullable=False),
        sa.Column('ai_reading_status', sa.String(length=32), nullable=False),
        *timestamps_and_id(),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_fortune_records_changed_hexagram_name'), 'fortune_records', ['changed_hexagram_name'], unique=False)
    op.create_index(op.f('ix_fortune_records_cast_at'), 'fortune_records', ['cast_at'], unique=False)
    op.create_index(op.f('ix_fortune_records_hexagram_name'), 'fortune_records', ['hexagram_name'], unique=False)
    op.create_index(op.f('ix_fortune_records_profile_id'), 'fortune_records', ['profile_id'], unique=False)
    op.create_index(op.f('ix_fortune_records_user_id'), 'fortune_records', ['user_id'], unique=False)
    op.create_index('ix_records_user_cast_at', 'fortune_records', ['user_id', 'cast_at'], unique=False)

    op.create_table(
        'notification_settings',
        sa.Column('user_id', _uuid_type(), nullable=False),
        sa.Column('system_enabled', sa.Boolean(), nullable=False),
        sa.Column('push_enabled', sa.Boolean(), nullable=False),
        sa.Column('daily_check_in', sa.Boolean(), nullable=False),
        sa.Column('reading_complete', sa.Boolean(), nullable=False),
        sa.Column('quiet_hours_enabled', sa.Boolean(), nullable=False),
        sa.Column('quiet_start', sa.String(length=5), nullable=False),
        sa.Column('quiet_end', sa.String(length=5), nullable=False),
        *timestamps_and_id(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index(op.f('ix_notification_settings_user_id'), 'notification_settings', ['user_id'], unique=False)

    op.create_table(
        'orders',
        sa.Column('user_id', _uuid_type(), nullable=False),
        sa.Column('plan', membership_plan, nullable=False),
        sa.Column('channel', order_channel, nullable=False),
        sa.Column('status', order_status, nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=12), nullable=False),
        sa.Column('provider_order_id', sa.String(length=255), nullable=True),
        sa.Column('raw_payload', _json_type(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        *timestamps_and_id(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('provider_order_id'),
    )
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)

    op.create_table(
        'verification_codes',
        sa.Column('destination', sa.String(length=255), nullable=False),
        sa.Column('channel', auth_provider, nullable=False),
        sa.Column('purpose', verification_purpose, nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        *timestamps_and_id(),
    )
    op.create_index(op.f('ix_verification_codes_destination'), 'verification_codes', ['destination'], unique=False)
    op.create_index('ix_verification_codes_destination_created', 'verification_codes', ['destination', 'created_at'], unique=False)

    op.create_table(
        'verification_notes',
        sa.Column('record_id', _uuid_type(), nullable=False),
        sa.Column('fulfilled', sa.Boolean(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('noted_at', sa.DateTime(timezone=True), nullable=False),
        *timestamps_and_id(),
        sa.ForeignKeyConstraint(['record_id'], ['fortune_records.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_verification_notes_record_id'), 'verification_notes', ['record_id'], unique=False)

    op.create_table(
        'audit_logs',
        sa.Column('actor_user_id', _uuid_type(), nullable=True),
        sa.Column('action', sa.String(length=120), nullable=False),
        sa.Column('target_type', sa.String(length=80), nullable=True),
        sa.Column('target_id', sa.String(length=80), nullable=True),
        sa.Column('metadata_json', _json_type(), nullable=True),
        *timestamps_and_id(),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_user_id'), 'audit_logs', ['actor_user_id'], unique=False)

    op.create_table(
        'admin_sessions',
        sa.Column('user_id', _uuid_type(), nullable=False),
        sa.Column('token_id', sa.String(length=80), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        *timestamps_and_id(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('token_id'),
    )
    op.create_index(op.f('ix_admin_sessions_token_id'), 'admin_sessions', ['token_id'], unique=False)
    op.create_index(op.f('ix_admin_sessions_user_id'), 'admin_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    for table in [
        'admin_sessions',
        'audit_logs',
        'verification_notes',
        'verification_codes',
        'orders',
        'notification_settings',
        'fortune_records',
        'profiles',
        'users',
    ]:
        op.drop_table(table)
    _drop_pg_enums('verificationpurpose', 'orderstatus', 'orderchannel', 'membershipstatus', 'membershipplan', 'authprovider')
