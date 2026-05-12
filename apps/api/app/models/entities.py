from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin, uuid_column_type


class MembershipPlan(StrEnum):
    trial = 'trial'
    monthly = 'monthly'
    yearly = 'yearly'


class MembershipStatus(StrEnum):
    trial = 'trial'
    active = 'active'
    expired = 'expired'
    cancelled = 'cancelled'


class AuthProvider(StrEnum):
    phone = 'phone'
    email = 'email'
    apple = 'apple'
    wechat = 'wechat'


class OrderChannel(StrEnum):
    apple = 'apple'
    wechat = 'wechat'
    alipay = 'alipay'
    mock = 'mock'


class OrderStatus(StrEnum):
    pending = 'pending'
    paid = 'paid'
    failed = 'failed'
    cancelled = 'cancelled'


class VerificationPurpose(StrEnum):
    login = 'login'
    bind = 'bind'


class FeedbackType(StrEnum):
    bug = 'bug'
    feature = 'feature'
    experience = 'experience'
    other = 'other'


class FeedbackStatus(StrEnum):
    open = 'open'
    reviewing = 'reviewing'
    resolved = 'resolved'
    ignored = 'ignored'


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'users'

    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    apple_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    wechat_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80), default='问事用户')
    avatar_url: Mapped[str | None] = mapped_column(Text)
    register_provider: Mapped[AuthProvider] = mapped_column(Enum(AuthProvider), default=AuthProvider.phone, nullable=False)
    membership_plan: Mapped[MembershipPlan] = mapped_column(Enum(MembershipPlan), default=MembershipPlan.trial, nullable=False)
    membership_status: Mapped[MembershipStatus] = mapped_column(Enum(MembershipStatus), default=MembershipStatus.trial, nullable=False)
    membership_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profiles: Mapped[list['Profile']] = relationship(back_populates='user', cascade='all, delete-orphan')
    records: Mapped[list['FortuneRecord']] = relationship(back_populates='user', cascade='all, delete-orphan')
    orders: Mapped[list['Order']] = relationship(back_populates='user', cascade='all, delete-orphan')
    feedback_items: Mapped[list['Feedback']] = relationship(back_populates='user', cascade='all, delete-orphan')


class Profile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'profiles'

    user_id: Mapped[str] = mapped_column(uuid_column_type(), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    relation: Mapped[str] = mapped_column(String(40), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    birthday: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates='profiles')
    records: Mapped[list['FortuneRecord']] = relationship(back_populates='profile')

    __table_args__ = (Index('ix_profiles_user_selected', 'user_id', 'is_selected'),)


class FortuneRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'fortune_records'

    user_id: Mapped[str] = mapped_column(uuid_column_type(), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    profile_id: Mapped[str | None] = mapped_column(uuid_column_type(), ForeignKey('profiles.id', ondelete='SET NULL'), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    hexagram_name: Mapped[str] = mapped_column(String(80), index=True)
    changed_hexagram_name: Mapped[str | None] = mapped_column(String(80), index=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ai_reading_status: Mapped[str] = mapped_column(String(32), default='not_requested', nullable=False)

    user: Mapped[User] = relationship(back_populates='records')
    profile: Mapped[Profile | None] = relationship(back_populates='records')
    notes: Mapped[list['VerificationNote']] = relationship(back_populates='record', cascade='all, delete-orphan')

    __table_args__ = (Index('ix_records_user_cast_at', 'user_id', 'cast_at'),)


class VerificationNote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'verification_notes'

    record_id: Mapped[str] = mapped_column(uuid_column_type(), ForeignKey('fortune_records.id', ondelete='CASCADE'), index=True)
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[str] = mapped_column(Text, default='', nullable=False)
    noted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    record: Mapped[FortuneRecord] = relationship(back_populates='notes')


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'orders'

    user_id: Mapped[str] = mapped_column(uuid_column_type(), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    plan: Mapped[MembershipPlan] = mapped_column(Enum(MembershipPlan), nullable=False)
    channel: Mapped[OrderChannel] = mapped_column(Enum(OrderChannel), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(12), default='CNY', nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates='orders')


class NotificationSetting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'notification_settings'

    user_id: Mapped[str] = mapped_column(uuid_column_type(), ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True)
    system_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    daily_check_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reading_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiet_start: Mapped[str] = mapped_column(String(5), default='22:00', nullable=False)
    quiet_end: Mapped[str] = mapped_column(String(5), default='08:00', nullable=False)


class VerificationCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'verification_codes'

    destination: Mapped[str] = mapped_column(String(255), index=True)
    channel: Mapped[AuthProvider] = mapped_column(Enum(AuthProvider), nullable=False)
    purpose: Mapped[VerificationPurpose] = mapped_column(Enum(VerificationPurpose), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index('ix_verification_codes_destination_created', 'destination', 'created_at'),)


class AuditLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'audit_logs'

    actor_user_id: Mapped[str | None] = mapped_column(uuid_column_type(), ForeignKey('users.id', ondelete='SET NULL'), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class AdminSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'admin_sessions'

    user_id: Mapped[str] = mapped_column(uuid_column_type(), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Feedback(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'feedback'

    user_id: Mapped[str] = mapped_column(uuid_column_type(), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    type: Mapped[FeedbackType] = mapped_column(Enum(FeedbackType), nullable=False, index=True)
    status: Mapped[FeedbackStatus] = mapped_column(Enum(FeedbackStatus), default=FeedbackStatus.open, nullable=False, index=True)
    starred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    screenshot_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(80))
    platform: Mapped[str | None] = mapped_column(String(40))
    device_info: Mapped[dict | None] = mapped_column(JSONB)

    user: Mapped[User] = relationship(back_populates='feedback_items')


class PortalVisit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'portal_visits'

    path: Mapped[str] = mapped_column(String(255), default='/', nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(12), index=True)
    referrer: Mapped[str | None] = mapped_column(Text)
    utm_source: Mapped[str | None] = mapped_column(String(120), index=True)
    utm_medium: Mapped[str | None] = mapped_column(String(120), index=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(160), index=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    session_id: Mapped[str | None] = mapped_column(String(80), index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (Index('ix_portal_visits_created_path', 'created_at', 'path'),)
