import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const ANALYTICS_RANGE_OPTIONS = [7, 14, 30, 60];
const PIE_COLORS = ['#2563eb', '#0f6b38', '#d97706', '#7c3aed', '#dc2626', '#64748b'];

type SectionKey = 'overview' | 'users' | 'revenue' | 'feedback' | 'portal' | 'logs';
type Stats = { users: number; records: number; orders: number; paid_orders: number; notes: number; feedback: number };
type User = { id: string; display_name: string; phone?: string; email?: string; membership_plan: string; membership_status: string; created_at: string };
type Order = { id: string; user_id: string; plan: string; channel: string; status: string; amount_cents: number; created_at: string };
type FeedbackItem = { id: string; user_id: string; user_display_name: string; user_contact?: string; type: string; status: string; starred: boolean; description: string; screenshot_urls: string[]; app_version?: string; platform?: string; created_at: string };
type FeedbackPage = { items: FeedbackItem[]; total: number; limit: number; offset: number };
type LogItem = { timestamp: string; level: string; event: string; logger: string; message: string; request_id?: string; status_code?: number; path?: string; duration_ms?: number; raw: Record<string, unknown> };
type LogPage = { items: LogItem[] };
type DailyPoint = { date: string; users: number; records: number; orders: number; revenue_cents: number; feedback: number };
type PortalDailyPoint = { date: string; visits: number; unique_visitors: number; sessions: number };
type DistributionItem = { label: string; count: number };
type PortalTraffic = {
  total_visits: number;
  unique_visitors: number;
  sessions: number;
  today_visits: number;
  daily: PortalDailyPoint[];
  path_distribution: DistributionItem[];
  language_distribution: DistributionItem[];
  referrer_distribution: DistributionItem[];
  source_distribution: DistributionItem[];
};
type ImagePreview = { urls: string[]; index: number };
type Analytics = {
  daily: DailyPoint[];
  revenue: { total_revenue_cents: number; paid_orders: number; pending_orders: number; monthly_revenue_cents: number; yearly_revenue_cents: number };
  users: {
    total_users: number;
    real_users: number;
    active_7d_users: number;
    active_30d_users: number;
    disabled_users: number;
    profile_completed_users: number;
    profile_completion_rate: number;
    total_profiles: number;
    average_profiles_per_user: number;
    self_profile_missing_users: number;
    login_providers: DistributionItem[];
    gender_distribution: DistributionItem[];
    membership_plans: DistributionItem[];
    membership_statuses: DistributionItem[];
  };
  feedback: {
    total_feedback: number;
    open_feedback: number;
    starred_feedback: number;
    screenshot_feedback: number;
    type_distribution: DistributionItem[];
    platform_distribution: DistributionItem[];
    status_distribution: DistributionItem[];
  };
};

async function api<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'content-type': 'application/json',
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('wenshi.admin.token') || '');
  const [username, setUsername] = useState('admin@wenshi.local');
  const [password, setPassword] = useState('admin123456');
  const [activeSection, setActiveSection] = useState<SectionKey>('overview');
  const [stats, setStats] = useState<Stats>();
  const [analytics, setAnalytics] = useState<Analytics>();
  const [portalTraffic, setPortalTraffic] = useState<PortalTraffic>();
  const [users, setUsers] = useState<User[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [feedbackTotal, setFeedbackTotal] = useState(0);
  const [feedbackSearch, setFeedbackSearch] = useState('');
  const [feedbackType, setFeedbackType] = useState('all');
  const [feedbackStatus, setFeedbackStatus] = useState('all');
  const [feedbackImages, setFeedbackImages] = useState<'all' | 'with' | 'without'>('all');
  const [feedbackStarred, setFeedbackStarred] = useState<'all' | 'starred' | 'unstarred'>('all');
  const [feedbackPage, setFeedbackPage] = useState(0);
  const [previewImage, setPreviewImage] = useState<ImagePreview | undefined>();
  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackItem | undefined>();
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [logLevel, setLogLevel] = useState('all');
  const [logSearch, setLogSearch] = useState('');
  const [selectedLog, setSelectedLog] = useState<LogItem | undefined>();
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [analyticsDays, setAnalyticsDays] = useState(14);
  const [loading, setLoading] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const authenticated = Boolean(token);
  const feedbackLimit = 12;
  const feedbackOffset = feedbackPage * feedbackLimit;
  const feedbackQuery = useMemo(() => {
    const params = new URLSearchParams({ limit: String(feedbackLimit), offset: String(feedbackOffset) });
    if (feedbackSearch.trim()) params.set('q', feedbackSearch.trim());
    if (feedbackType !== 'all') params.set('feedback_type', feedbackType);
    if (feedbackStatus !== 'all') params.set('feedback_status', feedbackStatus);
    if (feedbackImages === 'with') params.set('has_images', 'true');
    if (feedbackImages === 'without') params.set('has_images', 'false');
    if (feedbackStarred === 'starred') params.set('starred', 'true');
    if (feedbackStarred === 'unstarred') params.set('starred', 'false');
    return params.toString();
  }, [feedbackImages, feedbackOffset, feedbackSearch, feedbackStarred, feedbackStatus, feedbackType]);
  const logsQuery = useMemo(() => {
    const params = new URLSearchParams({ limit: '300' });
    if (logLevel !== 'all') params.set('level', logLevel);
    if (logSearch.trim()) params.set('q', logSearch.trim());
    return params.toString();
  }, [logLevel, logSearch]);

  async function login(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const data = await api<{ access_token: string }>('/api/v1/admin/login', undefined, {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      setToken(data.access_token);
      localStorage.setItem('wenshi.admin.token', data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败');
    }
  }

  function showToast(message: string) {
    setToast(message);
  }

  async function load() {
    if (!token) return;
    setError('');
    setLoading(true);
    try {
      const [statsData, analyticsData, usersData, ordersData, feedbackData] = await Promise.all([
        api<Stats>('/api/v1/admin/stats', token),
        api<Analytics>(`/api/v1/admin/analytics?days=${analyticsDays}`, token),
        api<User[]>('/api/v1/admin/users?limit=12', token),
        api<Order[]>('/api/v1/admin/orders?limit=12', token),
        api<FeedbackPage>(`/api/v1/admin/feedback?${feedbackQuery}`, token),
      ]);
      setStats(statsData);
      setAnalytics(analyticsData);
      setUsers(usersData);
      setOrders(ordersData);
      setFeedback(feedbackData.items);
      setFeedbackTotal(feedbackData.total);
    } catch (err) {
      showToast(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }

  async function loadPortalTraffic() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await api<PortalTraffic>(`/api/v1/admin/portal-traffic?days=${analyticsDays}`, token);
      setPortalTraffic(data);
    } catch (err) {
      showToast(err instanceof Error ? err.message : '门户访问数据加载失败');
    } finally {
      setLoading(false);
    }
  }

  async function loadFeedback() {
    if (!token) return;
    setError('');
    setFeedbackLoading(true);
    try {
      const feedbackData = await api<FeedbackPage>(`/api/v1/admin/feedback?${feedbackQuery}`, token);
      setFeedback(feedbackData.items);
      setFeedbackTotal(feedbackData.total);
    } catch (err) {
      showToast(err instanceof Error ? err.message : '反馈加载失败');
    } finally {
      setFeedbackLoading(false);
    }
  }

  async function toggleFeedbackStar(item: FeedbackItem) {
    if (!token) return;
    const nextStarred = !item.starred;
    const previousFeedback = feedback;
    const previousSelected = selectedFeedback;
    setFeedback(current => current.map(row => row.id === item.id ? { ...row, starred: nextStarred } : row));
    setSelectedFeedback(current => current?.id === item.id ? { ...current, starred: nextStarred } : current);
    setAnalytics(current => current ? {
      ...current,
      feedback: {
        ...current.feedback,
        starred_feedback: current.feedback.starred_feedback + (nextStarred ? 1 : -1),
      },
    } : current);
    try {
      const updated = await api<FeedbackItem>(`/api/v1/admin/feedback/${item.id}/star`, token, {
        method: 'PATCH',
        body: JSON.stringify({ starred: nextStarred }),
      });
      setFeedback(current => current.map(row => row.id === updated.id ? updated : row));
      setSelectedFeedback(current => current?.id === updated.id ? updated : current);
    } catch (err) {
      setFeedback(previousFeedback);
      setSelectedFeedback(previousSelected);
      showToast(err instanceof Error ? err.message : '收藏失败');
    }
  }

  async function updateFeedbackStatus(item: FeedbackItem, nextStatus: string) {
    if (!token || item.status === nextStatus) return;
    const previousFeedback = feedback;
    const previousSelected = selectedFeedback;
    setFeedback(current => current.map(row => row.id === item.id ? { ...row, status: nextStatus } : row));
    setSelectedFeedback(current => current?.id === item.id ? { ...current, status: nextStatus } : current);
    try {
      const updated = await api<FeedbackItem>(`/api/v1/admin/feedback/${item.id}/status`, token, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      });
      setFeedback(current => current.map(row => row.id === updated.id ? updated : row));
      setSelectedFeedback(current => current?.id === updated.id ? updated : current);
      setAnalytics(current => current ? {
        ...current,
        feedback: {
          ...current.feedback,
          status_distribution: updateDistribution(current.feedback.status_distribution, item.status, updated.status),
          open_feedback: current.feedback.open_feedback + (item.status === 'open' ? -1 : 0) + (updated.status === 'open' ? 1 : 0),
        },
      } : current);
    } catch (err) {
      setFeedback(previousFeedback);
      setSelectedFeedback(previousSelected);
      showToast(err instanceof Error ? err.message : '状态更新失败');
    }
  }

  async function loadLogs() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await api<LogPage>(`/api/v1/admin/logs?${logsQuery}`, token);
      setLogs(data.items);
    } catch (err) {
      showToast(err instanceof Error ? err.message : '日志加载失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [token, analyticsDays]);
  useEffect(() => { loadFeedback(); }, [feedbackQuery, token]);
  useEffect(() => { if (activeSection === 'portal') loadPortalTraffic(); }, [activeSection, analyticsDays, token]);
  useEffect(() => { if (activeSection === 'logs') loadLogs(); }, [activeSection, logsQuery, token]);
  useEffect(() => { setFeedbackPage(0); }, [feedbackSearch, feedbackType, feedbackStatus, feedbackImages, feedbackStarred]);
  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(''), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const statCards = useMemo<Array<[string, number, string]>>(() => [
    ['用户', stats?.users ?? 0, '累计注册用户'],
    ['卦象记录', stats?.records ?? 0, '用户保存的卦象'],
    ['订单', stats?.orders ?? 0, '全部订单'],
    ['已支付', stats?.paid_orders ?? 0, '成功支付订单'],
    ['验事批注', stats?.notes ?? 0, '历史应验记录'],
    ['意见反馈', stats?.feedback ?? 0, '用户提交问题'],
  ], [stats]);

  if (!authenticated) {
    return <main className="login-page">
      <form className="login-card" onSubmit={login}>
        <div className="brand">问事 Admin</div>
        <h1>商业化服务后台</h1>
        <label>账号<input value={username} onChange={event => setUsername(event.target.value)} /></label>
        <label>密码<input type="password" value={password} onChange={event => setPassword(event.target.value)} /></label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit">进入后台</button>
      </form>
    </main>;
  }

  return <main className="admin-shell">
    <aside className="sidebar">
      <div className="side-brand"><span>问</span><div><strong>问事 Admin</strong><small>服务与监控</small></div></div>
      <nav>
        {[
          ['overview', '总览'],
          ['users', '用户'],
          ['revenue', '盈利'],
          ['feedback', '反馈'],
          ['portal', '门户'],
          ['logs', '日志'],
        ].map(([key, label]) => <button key={key} className={activeSection === key ? 'active' : ''} onClick={() => setActiveSection(key as SectionKey)}>{label}</button>)}
      </nav>
      <button className="logout" onClick={() => { localStorage.removeItem('wenshi.admin.token'); setToken(''); }}>退出登录</button>
    </aside>

    <section className={activeSection === 'overview' ? 'dashboard dashboard-scroll' : 'dashboard'}>
      <header>
        <div><span className="brand">Dashboard</span><h1>{sectionTitle(activeSection)}</h1></div>
        <div className="actions"><button disabled={loading} onClick={activeSection === 'logs' ? loadLogs : activeSection === 'portal' ? loadPortalTraffic : load}>{loading ? '刷新中' : '刷新数据'}</button></div>
      </header>
      {toast ? <div className="toast" role="status">{toast}</div> : null}
      {activeSection === 'overview' ? <Overview statCards={statCards} analytics={analytics} analyticsDays={analyticsDays} onAnalyticsDaysChange={setAnalyticsDays} orders={orders} feedback={feedback} onPreview={setPreviewImage} /> : null}
      {activeSection === 'users' ? <UsersSection users={users} analytics={analytics} analyticsDays={analyticsDays} onAnalyticsDaysChange={setAnalyticsDays} /> : null}
      {activeSection === 'revenue' ? <RevenueSection analytics={analytics} analyticsDays={analyticsDays} onAnalyticsDaysChange={setAnalyticsDays} orders={orders} /> : null}
      {activeSection === 'portal' ? <PortalSection traffic={portalTraffic} analyticsDays={analyticsDays} onAnalyticsDaysChange={setAnalyticsDays} /> : null}
      {activeSection === 'logs' ? <LogsSection logs={logs} level={logLevel} search={logSearch} onLevelChange={setLogLevel} onSearchChange={setLogSearch} onSelect={setSelectedLog} /> : null}
      {activeSection === 'feedback' ? <FeedbackSection
        feedback={feedback}
        total={feedbackTotal}
        limit={feedbackLimit}
        page={feedbackPage}
        search={feedbackSearch}
        type={feedbackType}
        status={feedbackStatus}
        images={feedbackImages}
        starred={feedbackStarred}
        loading={feedbackLoading}
        analytics={analytics}
        onSearch={setFeedbackSearch}
        onTypeChange={setFeedbackType}
        onStatusChange={setFeedbackStatus}
        onImagesChange={setFeedbackImages}
        onStarredChange={setFeedbackStarred}
        onPageChange={setFeedbackPage}
        onPreview={setPreviewImage}
        onSelect={setSelectedFeedback}
        onToggleStar={toggleFeedbackStar}
      /> : null}
      {loading ? <div className="loading-overlay"><div><i /><strong>正在刷新数据</strong><span>请稍等片刻</span></div></div> : null}
    </section>

    {previewImage ? <ImageModal preview={previewImage} onChange={setPreviewImage} onClose={() => setPreviewImage(undefined)} /> : null}
    {selectedFeedback ? <FeedbackDetailModal
      item={selectedFeedback}
      onClose={() => setSelectedFeedback(undefined)}
      onPreview={setPreviewImage}
      onToggleStar={toggleFeedbackStar}
      onStatusChange={updateFeedbackStatus}
    /> : null}
    {selectedLog ? <LogDetailModal item={selectedLog} onClose={() => setSelectedLog(undefined)} /> : null}
  </main>;
}

function Overview({ statCards, analytics, analyticsDays, onAnalyticsDaysChange, orders, feedback, onPreview }: { statCards: Array<[string, number, string]>; analytics?: Analytics; analyticsDays: number; onAnalyticsDaysChange: (days: number) => void; orders: Order[]; feedback: FeedbackItem[]; onPreview: (preview: ImagePreview) => void }) {
  return <>
    <section className="stats">{statCards.map(([label, value, hint]) => <article key={label}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>)}</section>
    <section className="wide-grid">
      <Panel title="用户增长趋势" action={<RangeTabs value={analyticsDays} onChange={onAnalyticsDaysChange} />}><LineChart data={analytics?.daily ?? []} field="users" color="#0f6b38" label="新增用户" /></Panel>
      <RevenueCard analytics={analytics} />
    </section>
    <section className="grid">
      <Panel title="最新订单">{orders.map(order => <Row key={order.id} title={`${order.plan} · ${money(order.amount_cents)}`} meta={order.channel} tag={order.status} />)}</Panel>
      <Panel title="最新反馈">{feedback.slice(0, 5).map(item => <FeedbackRow key={item.id} item={item} onPreview={onPreview} />)}</Panel>
    </section>
  </>;
}

function UsersSection({ users, analytics, analyticsDays, onAnalyticsDaysChange }: { users: User[]; analytics?: Analytics; analyticsDays: number; onAnalyticsDaysChange: (days: number) => void }) {
  const userStats = analytics?.users;
  return <>
    <section className="user-metrics">
      <MetricCard label="真实用户" value={userStats?.real_users ?? 0} hint={`总账号 ${userStats?.total_users ?? 0}`} />
      <MetricCard label="7 日活跃" value={userStats?.active_7d_users ?? 0} hint={`30 日活跃 ${userStats?.active_30d_users ?? 0}`} />
      <MetricCard label="资料完成率" value={`${userStats?.profile_completion_rate ?? 0}%`} hint={`已完善 ${userStats?.profile_completed_users ?? 0}`} />
      <MetricCard label="平均档案数" value={userStats?.average_profiles_per_user ?? 0} hint={`档案总数 ${userStats?.total_profiles ?? 0}`} />
      <MetricCard label="缺本人档案" value={userStats?.self_profile_missing_users ?? 0} hint="需要引导补全" />
      <MetricCard label="注销/禁用" value={userStats?.disabled_users ?? 0} hint="不可登录账号" />
    </section>
    <section className="user-top-grid">
      <Panel title="用户增长趋势" action={<RangeTabs value={analyticsDays} onChange={onAnalyticsDaysChange} />}><LineChart data={analytics?.daily ?? []} field="users" color="#2563eb" label="新增用户" /></Panel>
      <Panel title="最新用户"><div className="scroll-list">{users.map(user => <Row key={user.id} title={user.display_name} meta={user.email || user.phone || user.id} tag={`${membershipPlanLabel(user.membership_plan)}/${membershipStatusLabel(user.membership_status)}`} />)}</div></Panel>
    </section>
    <section className="pie-row">
      <Panel title="登录方式统计"><PieChart items={userStats?.login_providers ?? []} labeler={providerLabel} /></Panel>
      <Panel title="性别统计"><PieChart items={userStats?.gender_distribution ?? []} labeler={genderLabel} /></Panel>
      <Panel title="来源平台"><PieChart items={analytics?.feedback.platform_distribution ?? []} labeler={platformLabel} /></Panel>
      <Panel title="会员方案"><PieChart items={userStats?.membership_plans ?? []} labeler={membershipPlanLabel} /></Panel>
    </section>
  </>;
}

function RevenueSection({ analytics, analyticsDays, onAnalyticsDaysChange, orders }: { analytics?: Analytics; analyticsDays: number; onAnalyticsDaysChange: (days: number) => void; orders: Order[] }) {
  return <>
    <section className="wide-grid"><RevenueCard analytics={analytics} /><Panel title="收入趋势" action={<RangeTabs value={analyticsDays} onChange={onAnalyticsDaysChange} />}><LineChart data={analytics?.daily ?? []} field="revenue_cents" color="#d97706" label="收入" moneyValues /></Panel></section>
    <section className="grid"><Panel title="最新订单">{orders.map(order => <Row key={order.id} title={`${order.plan} · ${money(order.amount_cents)}`} meta={order.channel} tag={order.status} />)}</Panel></section>
  </>;
}

function PortalSection({ traffic, analyticsDays, onAnalyticsDaysChange }: { traffic?: PortalTraffic; analyticsDays: number; onAnalyticsDaysChange: (days: number) => void }) {
  return <>
    <section className="portal-metrics">
      <MetricCard label="访问量 PV" value={traffic?.total_visits ?? 0} hint={`最近 ${analyticsDays} 天`} />
      <MetricCard label="独立访客 UV" value={traffic?.unique_visitors ?? 0} hint="按匿名 IP 哈希统计" />
      <MetricCard label="访问会话" value={traffic?.sessions ?? 0} hint="按浏览器会话统计" />
      <MetricCard label="今日访问" value={traffic?.today_visits ?? 0} hint="自然日 PV" />
    </section>
    <section className="wide-grid portal-wide-grid">
      <Panel title="门户访问趋势" action={<RangeTabs value={analyticsDays} onChange={onAnalyticsDaysChange} />}>
        <PortalLineChart data={traffic?.daily ?? []} />
      </Panel>
      <Panel title="访问路径"><div className="scroll-list">{(traffic?.path_distribution ?? []).map(item => <Row key={item.label} title={item.label} meta="页面路径" tag={`${item.count} PV`} />)}</div></Panel>
    </section>
    <section className="pie-row">
      <Panel title="语言分布"><PieChart items={traffic?.language_distribution ?? []} labeler={languageLabel} /></Panel>
      <Panel title="UTM 来源"><PieChart items={traffic?.source_distribution ?? []} labeler={sourceLabel} /></Panel>
      <Panel title="访问来源"><PieChart items={traffic?.referrer_distribution ?? []} labeler={referrerLabel} /></Panel>
      <Panel title="路径占比"><PieChart items={traffic?.path_distribution ?? []} /></Panel>
    </section>
  </>;
}

function LogsSection({ logs, level, search, onLevelChange, onSearchChange, onSelect }: { logs: LogItem[]; level: string; search: string; onLevelChange: (value: string) => void; onSearchChange: (value: string) => void; onSelect: (item: LogItem) => void }) {
  return <section className="logs-panel">
    <div className="logs-toolbar">
      <div className="filter-group">
        {['all', 'info', 'warning', 'error', 'critical'].map(value => <button key={value} className={level === value ? 'active' : ''} onClick={() => onLevelChange(value)}>{logLevelLabel(value)}</button>)}
      </div>
      <input value={search} onChange={event => onSearchChange(event.target.value)} placeholder="搜索 event、path、request_id、错误信息" />
    </div>
    <div className="logs-list">
      {logs.length ? logs.map((item, index) => <button key={`${item.timestamp}-${item.request_id || index}`} className="log-row" onClick={() => onSelect(item)}>
        <span className={`log-level ${item.level}`}>{item.level || '-'}</span>
        <strong>{item.event || item.message || '-'}</strong>
        <span>{item.path || '-'}</span>
        <em>{item.status_code ?? '-'}</em>
        <span>{item.duration_ms != null ? `${item.duration_ms}ms` : '-'}</span>
        <code>{item.request_id || '-'}</code>
        <time>{formatDateTime(item.timestamp)}</time>
      </button>) : <div className="empty-state">暂无日志</div>}
    </div>
  </section>;
}

function FeedbackSection({
  feedback,
  total,
  limit,
  page,
  search,
  type,
  status,
  images,
  starred,
  loading,
  analytics,
  onSearch,
  onTypeChange,
  onStatusChange,
  onImagesChange,
  onStarredChange,
  onPageChange,
  onPreview,
  onSelect,
  onToggleStar,
}: {
  feedback: FeedbackItem[];
  total: number;
  limit: number;
  page: number;
  search: string;
  type: string;
  status: string;
  images: 'all' | 'with' | 'without';
  starred: 'all' | 'starred' | 'unstarred';
  loading: boolean;
  analytics?: Analytics;
  onSearch: (value: string) => void;
  onTypeChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onImagesChange: (value: 'all' | 'with' | 'without') => void;
  onStarredChange: (value: 'all' | 'starred' | 'unstarred') => void;
  onPageChange: (value: number) => void;
  onPreview: (preview: ImagePreview) => void;
  onSelect: (item: FeedbackItem) => void;
  onToggleStar: (item: FeedbackItem) => void;
}) {
  const stats = analytics?.feedback;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const searchRef = useRef<HTMLDivElement>(null);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    function closeSearch(event: PointerEvent) {
      if (!searchRef.current?.contains(event.target as Node)) setSearchOpen(false);
    }
    document.addEventListener('pointerdown', closeSearch);
    return () => document.removeEventListener('pointerdown', closeSearch);
  }, []);

  return <section className="feedback-workbench">
    <section className="feedback-main">
      <div className="feedback-toolbar">
        <div ref={searchRef} className={`${searchOpen ? 'search-popover active' : 'search-popover'}${search ? ' has-value' : ''}`}>
          <button className="search-trigger" type="button" aria-label="搜索反馈" title="搜索反馈" onClick={() => setSearchOpen(open => !open)}>⌕</button>
          <div className="search-panel">
            <label>搜索反馈<input value={search} onChange={event => onSearch(event.target.value)} placeholder="描述、用户、手机号、邮箱" /></label>
            {search ? <button className="search-clear" type="button" onClick={() => onSearch('')}>清空</button> : null}
          </div>
        </div>
        <div className="filter-group">
          {[
            ['all', '全部类型'],
            ['bug', 'Bug'],
            ['feature', '功能'],
            ['experience', '体验'],
            ['other', '其他'],
          ].map(([value, label]) => <button key={value} className={type === value ? 'active' : ''} onClick={() => onTypeChange(value)}>{label}</button>)}
        </div>
        <div className="filter-group image-filter">
          {[
            ['all', '全部'],
            ['with', '有图片'],
            ['without', '无图片'],
          ].map(([value, label]) => <button key={value} className={images === value ? 'active' : ''} onClick={() => onImagesChange(value as 'all' | 'with' | 'without')}>{label}</button>)}
        </div>
        <div className="filter-group star-filter">
          {[
            ['all', '全部收藏'],
            ['starred', '已收藏'],
            ['unstarred', '未收藏'],
          ].map(([value, label]) => <button key={value} className={starred === value ? 'active' : ''} onClick={() => onStarredChange(value as 'all' | 'starred' | 'unstarred')}>{label}</button>)}
        </div>
        <div className="filter-group status-filter">
          {[
            ['all', '全部进度'],
            ['open', '待处理'],
            ['reviewing', '处理中'],
            ['resolved', '已解决'],
            ['ignored', '已忽略'],
          ].map(([value, label]) => <button key={value} className={status === value ? 'active' : ''} onClick={() => onStatusChange(value)}>{label}</button>)}
        </div>
      </div>
      <div className="feedback-list-wrap">
        <div className="feedback-list large">{feedback.map(item => <FeedbackRow key={item.id} item={item} onPreview={onPreview} onSelect={onSelect} onToggleStar={onToggleStar} />)}</div>
        {loading ? <div className="feedback-loading"><i /><span>正在更新反馈列表</span></div> : null}
      </div>
      <div className="pagination">
        <span>共 {total} 条 · 第 {page + 1} / {totalPages} 页</span>
        <div>
          <button disabled={page <= 0} onClick={() => onPageChange(Math.max(0, page - 1))}>上一页</button>
          <button disabled={page >= totalPages - 1} onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}>下一页</button>
        </div>
      </div>
    </section>
    <section className="feedback-stats-side">
      <section className="feedback-metrics compact">
        <MetricCard label="反馈总数" value={stats?.total_feedback ?? 0} />
        <MetricCard label="待处理" value={stats?.open_feedback ?? 0} />
        <MetricCard label="已收藏" value={stats?.starred_feedback ?? 0} />
        <MetricCard label="带截图" value={stats?.screenshot_feedback ?? 0} />
      </section>
      <section className="feedback-charts compact">
        <Panel title="反馈种类"><PieChart items={stats?.type_distribution ?? []} labeler={feedbackTypeLabel} /></Panel>
        <Panel title="来源平台"><PieChart items={stats?.platform_distribution ?? []} labeler={platformLabel} /></Panel>
        <Panel title="处理状态"><PieChart items={stats?.status_distribution ?? []} labeler={feedbackStatusLabel} /></Panel>
      </section>
    </section>
  </section>;
}

function Panel({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return <section className="panel"><div className="panel-head"><h2>{title}</h2>{action}</div><div className="list">{children}</div></section>;
}

function RevenueCard({ analytics }: { analytics?: Analytics }) {
  const revenue = analytics?.revenue;
  return <section className="panel revenue-panel">
    <h2>盈利面板</h2>
    <strong>{money(revenue?.total_revenue_cents ?? 0)}</strong>
    <div className="revenue-metrics">
      <span>已支付订单 <b>{revenue?.paid_orders ?? 0}</b></span>
      <span>待支付订单 <b>{revenue?.pending_orders ?? 0}</b></span>
      <span>月度收入 <b>{money(revenue?.monthly_revenue_cents ?? 0)}</b></span>
      <span>年度收入 <b>{money(revenue?.yearly_revenue_cents ?? 0)}</b></span>
    </div>
  </section>;
}

function MetricCard({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return <article><span>{label}</span><strong>{value}</strong>{hint ? <small>{hint}</small> : null}</article>;
}

function RangeTabs({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return <div className="range-tabs">
    {ANALYTICS_RANGE_OPTIONS.map(days => <button key={days} className={value === days ? 'active' : ''} onClick={() => onChange(days)}>{days} 天</button>)}
  </div>;
}

function PieChart({ items, labeler }: { items: DistributionItem[]; labeler?: (label: string) => string }) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  if (!items.length) return <div className="empty-state">暂无数据</div>;
  let cursor = 0;
  const segments = items.map((item, index) => {
    const percent = total ? item.count / total : 0;
    const start = cursor;
    cursor += percent * 100;
    return {
      ...item,
      color: PIE_COLORS[index % PIE_COLORS.length],
      percent,
      dashArray: `${percent * 100} ${100 - percent * 100}`,
      dashOffset: 25 - start,
    };
  });
  return <div className="pie-wrap">
    <div className="pie-visual">
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <circle className="pie-base" cx="21" cy="21" r="15.915" />
        {segments.map(segment => <circle
          key={segment.label}
          className="pie-segment"
          cx="21"
          cy="21"
          r="15.915"
          stroke={segment.color}
          strokeDasharray={segment.dashArray}
          strokeDashoffset={segment.dashOffset}
        />)}
      </svg>
      <div className="pie-center"><strong>{total}</strong><span>总计</span></div>
    </div>
    <div className="pie-legend">
      {segments.map(segment => {
        const label = labeler ? labeler(segment.label) : segment.label;
        return <div key={segment.label} className="legend-row">
          <i style={{ background: segment.color }} />
          <span>{label}</span>
          <b>{segment.count} · {Math.round(segment.percent * 100)}%</b>
        </div>;
      })}
    </div>
  </div>;
}

function LineChart({ data, field, color, label, moneyValues = false }: { data: DailyPoint[]; field: keyof DailyPoint; color: string; label: string; moneyValues?: boolean }) {
  if (!data.length) return <div className="chart"><div className="chart-meta"><span>{label} · 最近 0 天</span><div><strong>{moneyValues ? money(0) : 0}</strong><em className="up">+0</em></div></div><div className="empty-state chart-empty">暂无数据</div></div>;
  const values = data.map(point => Number(point[field]) || 0);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const width = 640;
  const height = 260;
  const padding = { top: 24, right: 20, bottom: 42, left: 54 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const range = Math.max(max - min, 1);
  const yTicks = Array.from({ length: 5 }, (_, index) => min + (range / 4) * index).reverse();
  const points = values.map((value, index) => {
    const x = padding.left + (values.length <= 1 ? chartWidth / 2 : (index / (values.length - 1)) * chartWidth);
    const y = padding.top + chartHeight - ((value - min) / range) * chartHeight;
    return `${x},${y}`;
  });
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point}`).join(' ');
  const areaPath = points.length ? `${path} L ${padding.left + chartWidth},${padding.top + chartHeight} L ${padding.left},${padding.top + chartHeight} Z` : '';
  const latest = values.length ? values[values.length - 1] : 0;
  const previous = values.length > 1 ? values[values.length - 2] : 0;
  const delta = latest - previous;
  const labelIndexes = data.map((_, index) => index).filter(index => data.length <= 8 || index === 0 || index === data.length - 1 || index % Math.ceil(data.length / 4) === 0);
  return <div className="chart">
    <div className="chart-meta">
      <span>{label} · 最近 {data.length || 0} 天</span>
      <div><strong>{moneyValues ? money(latest) : latest}</strong><em className={delta >= 0 ? 'up' : 'down'}>{delta >= 0 ? '+' : ''}{moneyValues ? money(delta) : delta}</em></div>
    </div>
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs><linearGradient id={`area-${field}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity=".22" /><stop offset="100%" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      {yTicks.map(tick => {
        const y = padding.top + chartHeight - ((tick - min) / range) * chartHeight;
        return <g key={tick}>
          <line className="grid-line" x1={padding.left} x2={padding.left + chartWidth} y1={y} y2={y} />
          <text className="axis-label" x={padding.left - 12} y={y + 4} textAnchor="end">{moneyValues ? money(Math.round(tick)) : Math.round(tick)}</text>
        </g>;
      })}
      {areaPath ? <path d={areaPath} fill={`url(#area-${field})`} /> : null}
      {path ? <path d={path} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" /> : null}
      {values.map((value, index) => {
        const x = padding.left + (values.length <= 1 ? chartWidth / 2 : (index / (values.length - 1)) * chartWidth);
        const y = padding.top + chartHeight - ((value - min) / range) * chartHeight;
        return <circle key={`${index}-${value}`} className="data-dot" cx={x} cy={y} r={index === values.length - 1 ? 5 : 3.5} fill={color}><title>{`${data[index]?.date}: ${moneyValues ? money(value) : value}`}</title></circle>;
      })}
      {labelIndexes.map(index => {
        const x = padding.left + (values.length <= 1 ? chartWidth / 2 : (index / (values.length - 1)) * chartWidth);
        const date = data[index]?.date.slice(5).replace('-', '/');
        return <text key={`${date}-${index}`} className="axis-label" x={x} y={height - 12} textAnchor="middle">{date}</text>;
      })}
    </svg>
  </div>;
}

function PortalLineChart({ data }: { data: PortalDailyPoint[] }) {
  if (!data.length) return <div className="chart"><div className="chart-meta"><span>PV / UV / 会话 · 最近 0 天</span><div><strong>0</strong><em className="up">+0</em></div></div><div className="empty-state chart-empty">暂无数据</div></div>;
  const fields: Array<{ key: keyof PortalDailyPoint; label: string; color: string }> = [
    { key: 'visits', label: 'PV', color: '#0f6b38' },
    { key: 'unique_visitors', label: 'UV', color: '#2563eb' },
    { key: 'sessions', label: '会话', color: '#d97706' },
  ];
  const max = Math.max(...data.flatMap(point => fields.map(field => Number(point[field.key]) || 0)), 1);
  const width = 640;
  const height = 260;
  const padding = { top: 24, right: 20, bottom: 42, left: 54 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const yTicks = Array.from({ length: 5 }, (_, index) => (max / 4) * index).reverse();
  const pathFor = (key: keyof PortalDailyPoint) => data.map((point, index) => {
    const value = Number(point[key]) || 0;
    const x = padding.left + (data.length <= 1 ? chartWidth / 2 : (index / (data.length - 1)) * chartWidth);
    const y = padding.top + chartHeight - (value / max) * chartHeight;
    return `${index === 0 ? 'M' : 'L'} ${x},${y}`;
  }).join(' ');
  const labelIndexes = data.map((_, index) => index).filter(index => data.length <= 8 || index === 0 || index === data.length - 1 || index % Math.ceil(data.length / 4) === 0);
  const latest = data[data.length - 1];
  return <div className="chart">
    <div className="chart-meta">
      <span>PV / UV / 会话 · 最近 {data.length} 天</span>
      <div><strong>{latest?.visits ?? 0}</strong><em className="up">今日 PV</em></div>
    </div>
    <div className="chart-legend-inline">{fields.map(field => <span key={field.key}><i style={{ background: field.color }} />{field.label}</span>)}</div>
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {yTicks.map(tick => {
        const y = padding.top + chartHeight - (tick / max) * chartHeight;
        return <g key={tick}>
          <line className="grid-line" x1={padding.left} x2={padding.left + chartWidth} y1={y} y2={y} />
          <text className="axis-label" x={padding.left - 12} y={y + 4} textAnchor="end">{Math.round(tick)}</text>
        </g>;
      })}
      {fields.map(field => <path key={field.key} d={pathFor(field.key)} fill="none" stroke={field.color} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />)}
      {labelIndexes.map(index => {
        const x = padding.left + (data.length <= 1 ? chartWidth / 2 : (index / (data.length - 1)) * chartWidth);
        const date = data[index]?.date.slice(5).replace('-', '/');
        return <text key={`${date}-${index}`} className="axis-label" x={x} y={height - 12} textAnchor="middle">{date}</text>;
      })}
    </svg>
  </div>;
}

function Row({ title, meta, tag }: { title: string; meta: string; tag: string }) {
  return <div className="row"><div><strong>{title}</strong><span>{meta}</span></div><em>{tag}</em></div>;
}

function FeedbackRow({ item, onPreview, onSelect, onToggleStar }: { item: FeedbackItem; onPreview: (preview: ImagePreview) => void; onSelect?: (item: FeedbackItem) => void; onToggleStar?: (item: FeedbackItem) => void }) {
  const imageUrls = item.screenshot_urls.map(resolveAssetUrl);
  const title = item.description.replace(/\s+/g, ' ').trim() || '未命名反馈';
  return <div className={onSelect ? 'feedback-row interactive' : 'feedback-row'} onClick={() => onSelect?.(item)}>
    <div className="feedback-head">
      <div className="feedback-tags">
        <em>{feedbackTypeLabel(item.type)}</em>
        <em>{feedbackStatusLabel(item.status)}</em>
        {onToggleStar ? <button className={item.starred ? 'star-button active' : 'star-button'} onClick={event => { event.stopPropagation(); onToggleStar(item); }}>{item.starred ? '★ 已收藏' : '☆ 收藏'}</button> : null}
      </div>
    </div>
    <p title={title}>{title}</p>
    <span>{item.user_display_name} · {item.user_contact || item.user_id} · {platformLabel(item.platform || '-')} · {new Date(item.created_at).toLocaleString()}</span>
    {imageUrls.length ? <div className="feedback-thumbs">{imageUrls.slice(0, 4).map((url, index) => <button key={url} onClick={event => { event.stopPropagation(); onPreview({ urls: imageUrls, index }); }}><img src={url} alt="反馈截图" /></button>)}</div> : null}
  </div>;
}

function FeedbackDetailModal({ item, onClose, onPreview, onToggleStar, onStatusChange }: { item: FeedbackItem; onClose: () => void; onPreview: (preview: ImagePreview) => void; onToggleStar: (item: FeedbackItem) => void; onStatusChange: (item: FeedbackItem, status: string) => void }) {
  const imageUrls = item.screenshot_urls.map(resolveAssetUrl);
  return <div className="detail-modal" onClick={onClose}>
    <section className="feedback-detail" onClick={event => event.stopPropagation()}>
      <button className="detail-close" onClick={onClose}>×</button>
      <div className="detail-head">
        <div>
          <span className="brand">Feedback Detail</span>
          <h2>{item.description.replace(/\s+/g, ' ').trim() || '未命名反馈'}</h2>
        </div>
        <button className={item.starred ? 'star-button active' : 'star-button'} onClick={() => onToggleStar(item)}>{item.starred ? '★ 已收藏' : '☆ 收藏'}</button>
      </div>
      <div className="detail-grid">
        <span><b>反馈类型</b>{feedbackTypeLabel(item.type)}</span>
        <span><b>用户</b>{item.user_display_name}</span>
        <span><b>联系方式</b>{item.user_contact || item.user_id}</span>
        <span><b>来源平台</b>{platformLabel(item.platform || '-')}</span>
        <span><b>App 版本</b>{item.app_version || '未提供'}</span>
        <span><b>提交时间</b>{new Date(item.created_at).toLocaleString()}</span>
      </div>
      <label className="status-editor">处理状态
        <select value={item.status} onChange={event => onStatusChange(item, event.target.value)}>
          {['open', 'reviewing', 'resolved', 'ignored'].map(value => <option key={value} value={value}>{feedbackStatusLabel(value)}</option>)}
        </select>
      </label>
      <div className="detail-description">
        <b>详细描述</b>
        <p>{item.description}</p>
      </div>
      <div className="detail-images">
        <b>附加截图</b>
        {imageUrls.length ? <div>{imageUrls.map((url, index) => <button key={url} onClick={() => onPreview({ urls: imageUrls, index })}><img src={url} alt="反馈截图" /></button>)}</div> : <span>暂无截图</span>}
      </div>
    </section>
  </div>;
}

function LogDetailModal({ item, onClose }: { item: LogItem; onClose: () => void }) {
  return <div className="detail-modal" onClick={onClose}>
    <section className="log-detail" onClick={event => event.stopPropagation()}>
      <button className="detail-close" onClick={onClose}>×</button>
      <div className="detail-head">
        <div>
          <span className="brand">Log Detail</span>
          <h2>{item.event || item.message || '日志详情'}</h2>
        </div>
        <span className={`log-level ${item.level}`}>{item.level || '-'}</span>
      </div>
      <div className="detail-grid">
        <span><b>时间</b>{formatDateTime(item.timestamp)}</span>
        <span><b>路径</b>{item.path || '-'}</span>
        <span><b>状态码</b>{item.status_code ?? '-'}</span>
        <span><b>耗时</b>{item.duration_ms != null ? `${item.duration_ms}ms` : '-'}</span>
        <span><b>Request ID</b>{item.request_id || '-'}</span>
        <span><b>Logger</b>{item.logger || '-'}</span>
      </div>
      <pre>{JSON.stringify(item.raw, null, 2)}</pre>
    </section>
  </div>;
}

function ImageModal({ preview, onChange, onClose }: { preview: ImagePreview; onChange: (preview: ImagePreview) => void; onClose: () => void }) {
  const imageUrl = preview.urls[preview.index];
  const canNavigate = preview.urls.length > 1;
  const showPrevious = () => onChange({ urls: preview.urls, index: (preview.index - 1 + preview.urls.length) % preview.urls.length });
  const showNext = () => onChange({ urls: preview.urls, index: (preview.index + 1) % preview.urls.length });
  return <div className="image-modal" onClick={onClose}>
    <div className="image-viewer" onClick={event => event.stopPropagation()}>
      <button className="image-close" onClick={onClose}>×</button>
      {canNavigate ? <button className="image-nav previous" onClick={showPrevious}>‹</button> : null}
      <img src={imageUrl} alt="反馈截图预览" />
      {canNavigate ? <button className="image-nav next" onClick={showNext}>›</button> : null}
      <div className="image-meta"><span>{preview.index + 1} / {preview.urls.length}</span><a href={imageUrl} target="_blank" rel="noreferrer">新窗口打开</a></div>
    </div>
  </div>;
}

function sectionTitle(section: SectionKey) {
  if (section === 'users') return '用户监控';
  if (section === 'revenue') return '盈利面板';
  if (section === 'feedback') return '用户反馈';
  if (section === 'portal') return '门户访问';
  if (section === 'logs') return '系统日志';
  return '运营总览';
}

function logLevelLabel(level: string) {
  if (level === 'all') return '全部';
  if (level === 'warning') return 'Warning';
  if (level === 'error') return 'Error';
  if (level === 'critical') return 'Critical';
  return 'Info';
}

function formatDateTime(value: string) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function feedbackTypeLabel(type: string) {
  if (type === 'bug') return 'Bug 反馈';
  if (type === 'feature') return '功能建议';
  if (type === 'experience') return '体验优化';
  return '其他';
}

function feedbackStatusLabel(status: string) {
  if (status === 'open') return '待处理';
  if (status === 'reviewing') return '处理中';
  if (status === 'resolved') return '已解决';
  if (status === 'ignored') return '已忽略';
  return status;
}

function platformLabel(platform: string) {
  if (platform === 'ios') return 'iOS';
  if (platform === 'android') return 'Android';
  if (platform === 'web') return 'Web';
  if (platform === '-') return '-';
  return platform || '未知来源';
}

function languageLabel(language?: string) {
  if (!language || language === 'direct') return '未识别';
  if (language === 'zh') return '中文';
  if (language === 'en') return 'English';
  return language;
}

function sourceLabel(source?: string) {
  if (!source || source === 'direct') return '直接访问';
  return source;
}

function referrerLabel(referrer?: string) {
  if (!referrer || referrer === 'direct') return '直接访问';
  try {
    return new URL(referrer).hostname;
  } catch {
    return referrer;
  }
}

function updateDistribution(items: DistributionItem[], previousLabel: string, nextLabel: string) {
  if (previousLabel === nextLabel) return items;
  const counts = new Map(items.map(item => [item.label, item.count]));
  counts.set(previousLabel, Math.max(0, (counts.get(previousLabel) ?? 0) - 1));
  counts.set(nextLabel, (counts.get(nextLabel) ?? 0) + 1);
  return Array.from(counts.entries())
    .filter(([, count]) => count > 0)
    .map(([label, count]) => ({ label, count }));
}

function resolveAssetUrl(url: string) {
  if (!url) return url;
  if (/^https?:\/\//.test(url)) return url;
  if (url.startsWith('/')) return `${API_BASE}${url}`;
  return url;
}

function providerLabel(provider: string) {
  if (provider === 'phone') return '手机号';
  if (provider === 'email') return '邮箱';
  if (provider === 'apple') return 'Apple';
  if (provider === 'wechat') return '微信';
  if (provider === 'google') return 'Google';
  return provider;
}

function genderLabel(gender: string) {
  if (gender === '男') return '男';
  if (gender === '女') return '女';
  return '未填写';
}

function membershipPlanLabel(plan: string) {
  if (plan === 'trial') return '试用';
  if (plan === 'monthly') return '月会员';
  if (plan === 'yearly') return '年会员';
  return plan;
}

function membershipStatusLabel(status: string) {
  if (status === 'trial') return '试用中';
  if (status === 'active') return '有效';
  if (status === 'expired') return '已过期';
  if (status === 'cancelled') return '已取消';
  return status;
}

function money(cents: number) {
  return `¥${(cents / 100).toFixed(2)}`;
}

createRoot(document.getElementById('root')!).render(<App />);
