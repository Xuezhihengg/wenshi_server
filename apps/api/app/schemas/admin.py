from datetime import datetime

from pydantic import BaseModel


class AdminStats(BaseModel):
    users: int
    records: int
    orders: int
    paid_orders: int
    notes: int
    feedback: int


class AdminUserItem(BaseModel):
    id: str
    phone: str | None
    email: str | None
    display_name: str
    membership_plan: str
    membership_status: str
    created_at: datetime
    last_login_at: datetime | None


class AdminOrderItem(BaseModel):
    id: str
    user_id: str
    plan: str
    channel: str
    status: str
    amount_cents: int
    created_at: datetime


class AdminRecordItem(BaseModel):
    id: str
    user_id: str
    question: str
    hexagram_name: str | None
    changed_hexagram_name: str | None
    favorite: bool
    cast_at: datetime


class AdminFeedbackItem(BaseModel):
    id: str
    user_id: str
    user_display_name: str
    user_contact: str | None
    type: str
    status: str
    starred: bool
    description: str
    screenshot_urls: list[str]
    app_version: str | None
    platform: str | None
    created_at: datetime


class AdminFeedbackPage(BaseModel):
    items: list[AdminFeedbackItem]
    total: int
    limit: int
    offset: int


class AdminFeedbackStarRequest(BaseModel):
    starred: bool


class AdminFeedbackStatusRequest(BaseModel):
    status: str


class AdminLogItem(BaseModel):
    timestamp: str
    level: str
    event: str
    logger: str
    message: str
    request_id: str | None
    status_code: int | None
    path: str | None
    duration_ms: float | None
    raw: dict


class AdminLogPage(BaseModel):
    items: list[AdminLogItem]


class AdminDailyPoint(BaseModel):
    date: str
    users: int
    records: int
    orders: int
    revenue_cents: int
    feedback: int


class AdminPortalDailyPoint(BaseModel):
    date: str
    visits: int
    unique_visitors: int
    sessions: int


class AdminRevenueSummary(BaseModel):
    total_revenue_cents: int
    paid_orders: int
    pending_orders: int
    monthly_revenue_cents: int
    yearly_revenue_cents: int


class AdminDistributionItem(BaseModel):
    label: str
    count: int


class AdminUserAnalytics(BaseModel):
    total_users: int
    real_users: int
    active_7d_users: int
    active_30d_users: int
    disabled_users: int
    profile_completed_users: int
    profile_completion_rate: float
    total_profiles: int
    average_profiles_per_user: float
    self_profile_missing_users: int
    login_providers: list[AdminDistributionItem]
    gender_distribution: list[AdminDistributionItem]
    membership_plans: list[AdminDistributionItem]
    membership_statuses: list[AdminDistributionItem]


class AdminFeedbackAnalytics(BaseModel):
    total_feedback: int
    open_feedback: int
    starred_feedback: int
    screenshot_feedback: int
    type_distribution: list[AdminDistributionItem]
    platform_distribution: list[AdminDistributionItem]
    status_distribution: list[AdminDistributionItem]


class AdminPortalTraffic(BaseModel):
    total_visits: int
    unique_visitors: int
    sessions: int
    today_visits: int
    daily: list[AdminPortalDailyPoint]
    path_distribution: list[AdminDistributionItem]
    language_distribution: list[AdminDistributionItem]
    referrer_distribution: list[AdminDistributionItem]
    source_distribution: list[AdminDistributionItem]


class AdminAnalytics(BaseModel):
    daily: list[AdminDailyPoint]
    revenue: AdminRevenueSummary
    users: AdminUserAnalytics
    feedback: AdminFeedbackAnalytics
