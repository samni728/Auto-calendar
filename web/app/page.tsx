"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type User = { id: string; email: string; display_name: string; role: string; workspace_id: string; workspace_name: string; must_change_password: boolean };
type Room = { id: string; code: string; room_type: string; floor: string };
type HotelEvent = { id: string; room_id: string | null; title: string; guest_name: string; event_type: string; status: string; start_date: string; end_date: string; notes: string; source_system: string; sync_status: string };
type Dashboard = { workspace_name: string; timezone: string; rooms: Room[]; events: HotelEvent[]; unassigned_count: number };
type Connection = { provider: "google" | "microsoft"; configured: boolean; status: string; account_email: string | null; selected_calendar_id: string | null; selected_calendar_name: string | null; last_sync_at: string | null; last_error: string | null };
type Calendar = { id: string; name: string; primary: boolean };

const api = async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
  const response = await fetch(path, { ...options, credentials: "include", headers: { "Content-Type": "application/json", ...options.headers } });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(payload.detail || `请求失败 (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
};

const iso = (value: Date) => [
  value.getFullYear(),
  String(value.getMonth() + 1).padStart(2, "0"),
  String(value.getDate()).padStart(2, "0"),
].join("-");
const addDays = (value: Date, days: number) => { const result = new Date(value); result.setDate(result.getDate() + days); return result; };
const today = (timeZone = "Asia/Shanghai") => {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const number = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
  return new Date(number("year"), number("month") - 1, number("day"));
};
const dateLabel = (value: Date) => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(value);

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState("admin@autocalendar.app");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setLoading(true); setError("");
    try { onLogin(await api<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) })); }
    catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  return <main className="login-shell">
    <section className="login-story">
      <div className="login-brand"><span>A</span><strong>Auto Calendar</strong></div>
      <div><p className="eyebrow light">为小型酒店设计的日历中台</p><h1>把分散的预订日历，<br />变成一张清楚的房态图。</h1><p>Google Calendar、Microsoft 365 与酒店房间在同一条时间轴上协作。</p></div>
      <div className="trust-row"><span>本地数据</span><span>加密凭据</span><span>响应式 PWA</span></div>
    </section>
    <section className="login-panel"><form className="login-card" onSubmit={submit}>
      <div className="mobile-brand"><span>A</span><strong>Auto Calendar</strong></div>
      <p className="eyebrow">酒店运营工作台</p><h2>登录账号</h2><p className="form-intro">使用管理员创建的账号进入。即使在受信网络中，应用账号仍然是必需的。</p>
      <label>邮箱<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required /></label>
      <label>密码<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required minLength={8} /></label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button login-button" disabled={loading}>{loading ? "正在登录…" : "安全登录"}</button>
      <p className="login-help">首次运行的临时密码保存在服务器 <code>.env</code> 中。</p>
    </form></section>
  </main>;
}

function PasswordPanel({ onChanged }: { onChanged: (user: User) => void }) {
  const [currentPassword, setCurrentPassword] = useState(""); const [newPassword, setNewPassword] = useState(""); const [message, setMessage] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setMessage("");
    try { const changed = await api<User>("/api/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }); onChanged(changed); setCurrentPassword(""); setNewPassword(""); setMessage("密码已更新"); }
    catch (reason) { setMessage((reason as Error).message); }
  };
  return <section className="settings-card"><div><p className="eyebrow">账号安全</p><h2>修改登录密码</h2><p>建议使用 12 位以上、只在本系统使用的密码。</p></div><form onSubmit={submit}>
    <label>当前密码<input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required /></label>
    <label>新密码<input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} minLength={12} required /></label>
    {message && <p className={message === "密码已更新" ? "form-success" : "form-error"}>{message}</p>}<button className="primary-button">保存新密码</button>
  </form></section>;
}

function Connections() {
  const [items, setItems] = useState<Connection[]>([]); const [calendars, setCalendars] = useState<Record<string, Calendar[]>>({}); const [message, setMessage] = useState("");
  const load = useCallback(() => api<Connection[]>("/api/connections").then(setItems).catch((e) => setMessage(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const connect = async (provider: string) => { try { const result = await api<{ authorization_url: string }>(`/api/oauth/${provider}/start`, { method: "POST" }); window.location.assign(result.authorization_url); } catch (reason) { setMessage((reason as Error).message); } };
  const getCalendars = async (provider: string) => { try { const available = await api<Calendar[]>(`/api/connections/${provider}/calendars`); setCalendars((old) => ({ ...old, [provider]: available })); } catch (reason) { setMessage((reason as Error).message); } };
  const selectCalendar = async (provider: string, value: string) => { const item = calendars[provider]?.find((calendar) => calendar.id === value); if (!item) return; try { await api(`/api/connections/${provider}/calendar`, { method: "PUT", body: JSON.stringify({ calendar_id: item.id, calendar_name: item.name }) }); await load(); setMessage(`已选择 ${item.name}`); } catch (reason) { setMessage((reason as Error).message); } };
  const sync = async (provider: string) => { try { const result = await api<{ synced: number }>(`/api/connections/${provider}/sync`, { method: "POST" }); setMessage(`同步完成：读取 ${result.synced} 条变更`); await load(); } catch (reason) { setMessage((reason as Error).message); } };
  return <section className="connections-page">
    <div className="page-heading"><div><p className="eyebrow">外部日历</p><h1>连接与同步</h1><p>授权只发生在 Google 或 Microsoft 页面，Client Secret 与 refresh token 只保存在服务端。</p></div></div>
    {message && <p className="notice-bar">{message}</p>}
    <div className="connection-grid">{items.map((item) => { const name = item.provider === "google" ? "Google Calendar" : "Microsoft 365"; return <article className="connection-card" key={item.provider}>
      <div className={`provider-logo ${item.provider}`}>{item.provider === "google" ? "G" : "M"}</div><div className="connection-title"><h2>{name}</h2><span className={`status ${item.status}`}>{item.status === "connected" ? "已连接" : "未连接"}</span></div>
      <p>{item.account_email || (item.configured ? "可以开始浏览器授权" : "服务端尚未填写 OAuth 配置")}</p>{item.selected_calendar_name && <p className="selected-calendar">同步日历：{item.selected_calendar_name}</p>}
      {item.status === "connected" ? <><div className="connection-actions"><button className="ghost-button" onClick={() => getCalendars(item.provider)}>选择日历</button><button className="primary-button" onClick={() => sync(item.provider)} disabled={!item.selected_calendar_id}>立即同步</button></div>{calendars[item.provider] && <select value={item.selected_calendar_id || ""} onChange={(e) => selectCalendar(item.provider, e.target.value)}><option value="">请选择一个日历</option>{calendars[item.provider].map((calendar) => <option value={calendar.id} key={calendar.id}>{calendar.name}{calendar.primary ? "（主日历）" : ""}</option>)}</select>}</> : <button className="primary-button wide" disabled={!item.configured} onClick={() => connect(item.provider)}>连接 {name}</button>}
    </article>; })}</div>
    <article className="architecture-note"><strong>同步链路</strong><span>浏览器授权 → 服务端保存 refresh token → 定时/手动读取日历 → 待分配区 → 绑定房间</span></article>
  </section>;
}

function EventDialog({ rooms, event, startDate, onClose, onSaved }: { rooms: Room[]; event?: HotelEvent | null; startDate: Date; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ room_id: event?.room_id || "", title: event?.title || "", guest_name: event?.guest_name || "", event_type: event?.event_type || "reservation", status: event?.status || "reserved", start_date: event?.start_date || iso(startDate), end_date: event?.end_date || iso(addDays(startDate, 1)), notes: event?.notes || "" });
  const [error, setError] = useState(""); const set = (key: string, value: string) => setForm((old) => ({ ...old, [key]: value }));
  const submit = async (e: FormEvent) => { e.preventDefault(); setError(""); try { await api(event ? `/api/events/${event.id}` : "/api/events", { method: event ? "PATCH" : "POST", body: JSON.stringify({ ...form, room_id: form.room_id || null }) }); onSaved(); onClose(); } catch (reason) { setError((reason as Error).message); } };
  const remove = async () => { if (!event || !window.confirm("确认删除这条事件？")) return; try { await api(`/api/events/${event.id}`, { method: "DELETE" }); onSaved(); onClose(); } catch (reason) { setError((reason as Error).message); } };
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="event-title">
    <div className="modal-head"><div><p className="eyebrow">房态事件</p><h2 id="event-title">{event ? "编辑事件" : "新建事件"}</h2></div><button onClick={onClose} aria-label="关闭">×</button></div><form onSubmit={submit}>
      <label className="full">事件名称<input value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="例如：王女士 · 官网预订" required /></label>
      <label>房间<select value={form.room_id} onChange={(e) => set("room_id", e.target.value)}><option value="">暂不分配</option>{rooms.map((room) => <option value={room.id} key={room.id}>{room.code} · {room.room_type}</option>)}</select></label>
      <label>客人姓名<input value={form.guest_name} onChange={(e) => set("guest_name", e.target.value)} /></label><label>开始日期<input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} required /></label><label>结束日期<input type="date" value={form.end_date} onChange={(e) => set("end_date", e.target.value)} required /></label>
      <label>类型<select value={form.event_type} onChange={(e) => set("event_type", e.target.value)}><option value="reservation">预订</option><option value="cleaning">清洁</option><option value="maintenance">维护</option><option value="blocked">锁房</option></select></label>
      <label>状态<select value={form.status} onChange={(e) => set("status", e.target.value)}><option value="reserved">已预订</option><option value="checked_in">已入住</option><option value="checked_out">已退房</option><option value="cleaning">清洁中</option><option value="maintenance">维护中</option><option value="blocked">已锁房</option></select></label>
      <label className="full">备注<textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={3} /></label>{error && <p className="form-error full">{error}</p>}
      <div className="modal-actions full">{event && <button type="button" className="danger-button" onClick={remove}>删除</button>}<span /><button type="button" className="ghost-button" onClick={onClose}>取消</button><button className="primary-button">保存事件</button></div>
    </form>
  </section></div>;
}

function DashboardView({ dashboard, startDate, onStartDate, onEdit, onNew }: { dashboard: Dashboard; startDate: Date; onStartDate: (date: Date) => void; onEdit: (event: HotelEvent) => void; onNew: () => void }) {
  const dates = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(startDate, index)), [startDate]); const current = iso(today());
  const dayEvents = dashboard.events.filter((event) => event.start_date <= current && event.end_date > current); const occupancy = dashboard.rooms.length ? Math.round(dayEvents.filter((e) => e.status === "checked_in" || e.status === "reserved").length / dashboard.rooms.length * 100) : 0;
  const tone = (event: HotelEvent) => event.status === "checked_in" ? "mint" : event.event_type === "cleaning" ? "amber" : event.event_type === "maintenance" || event.event_type === "blocked" ? "rose" : event.source_system === "microsoft" ? "violet" : "blue";
  const position = (event: HotelEvent) => { const start = Math.max(0, Math.round((new Date(`${event.start_date}T00:00:00`).getTime() - startDate.getTime()) / 86400000)); const end = Math.min(7, Math.round((new Date(`${event.end_date}T00:00:00`).getTime() - startDate.getTime()) / 86400000)); return { gridColumn: `${start + 1} / ${Math.max(start + 2, end + 1)}` }; };
  return <><header className="topbar"><div><p className="eyebrow">{dateLabel(today())}</p><h1>房态总览</h1></div><div className="top-actions"><button className="primary-button" onClick={onNew}><span>＋</span> 新建事件</button></div></header>
    <section className="metrics"><article className="metric-card accent-blue"><p>今日在店</p><strong>{dayEvents.filter((e) => e.status === "checked_in").length}</strong><span>已办理入住</span></article><article className="metric-card accent-green"><p>今日有安排</p><strong>{dayEvents.length}</strong><span>预订、清洁与维护</span></article><article className="metric-card accent-orange"><p>房间占用率</p><strong>{occupancy}%</strong><span>按今日房态估算</span></article><article className="metric-card accent-red"><p>待分配</p><strong>{dashboard.unassigned_count}</strong><span>来自外部日历或手动录入</span></article></section>
    {dashboard.unassigned_count > 0 && <div className="unassigned-banner"><span><strong>{dashboard.unassigned_count} 条事件等待分配房间</strong><small>外部日历事件不会自动占用房间，避免误配。</small></span></div>}
    <section className="timeline-card"><div className="timeline-toolbar"><div><div className="section-title-row"><h2>房间时间轴</h2><span className="live-pill"><i />数据已保存</span></div><p>{dashboard.workspace_name} · 未来 7 天</p></div><div className="toolbar-actions"><button className="ghost-button" onClick={() => onStartDate(today())}>今天</button><div className="segment"><button onClick={() => onStartDate(addDays(startDate, -7))}>‹</button><button onClick={() => onStartDate(addDays(startDate, 7))}>›</button></div></div></div>
      <div className="timeline-scroll" role="region" aria-label="房间未来七天占用情况"><div className="timeline-grid"><div className="room-heading">房间</div><div className="date-headings">{dates.map((date) => <div className={iso(date) === current ? "today" : ""} key={iso(date)}><span>{new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(date)}</span><strong>{date.getDate()}</strong></div>)}</div>
        {dashboard.rooms.map((room) => <div className="room-row" key={room.id}><div className="room-label"><strong>{room.code}</strong><span>{room.room_type}</span></div><div className="room-days">{dates.map((date) => <span key={iso(date)} />)}{dashboard.events.filter((event) => event.room_id === room.id && event.start_date < iso(addDays(startDate, 7)) && event.end_date > iso(startDate)).map((event) => <button className={`booking booking-${tone(event)}`} style={position(event)} key={event.id} onClick={() => onEdit(event)}><b>{event.title}</b><small>{event.source_system === "local" ? "本地" : event.source_system} · {event.status}</small></button>)}</div></div>)}</div></div>
      <div className="timeline-legend"><span><i className="legend-mint" />已入住</span><span><i className="legend-blue" />已预订</span><span><i className="legend-amber" />清洁</span><span><i className="legend-rose" />维护 / 锁房</span></div></section>
  </>;
}

export default function Home() {
  const [user, setUser] = useState<User | null | undefined>(undefined); const [dashboard, setDashboard] = useState<Dashboard | null>(null); const [view, setView] = useState<"overview" | "connections" | "settings">("overview"); const [startDate, setStartDate] = useState(today()); const [dialog, setDialog] = useState<HotelEvent | null | "new">(null); const [error, setError] = useState("");
  const loadDashboard = useCallback(() => api<Dashboard>(`/api/dashboard?start=${iso(startDate)}&days=14`).then(setDashboard).catch((e) => setError(e.message)), [startDate]);
  useEffect(() => { api<User>("/api/auth/me").then(setUser).catch(() => setUser(null)); }, []); useEffect(() => { if (user) loadDashboard(); }, [user, loadDashboard]);
  if (user === undefined) return <main className="loading-screen"><span>A</span><p>正在打开酒店工作台…</p></main>; if (!user) return <Login onLogin={setUser} />;
  const logout = async () => { await api("/api/auth/logout", { method: "POST" }); setUser(null); };
  return <main className="app-shell"><aside className="sidebar"><div className="brand-mark"><span className="brand-symbol">A</span><span><strong>Auto Calendar</strong><small>酒店运营中心</small></span></div><nav className="main-nav"><button className={`nav-item ${view === "overview" ? "active" : ""}`} onClick={() => setView("overview")}><span>⌂</span>房态总览</button><button className={`nav-item ${view === "connections" ? "active" : ""}`} onClick={() => setView("connections")}><span>↗</span>日历连接</button><button className={`nav-item ${view === "settings" ? "active" : ""}`} onClick={() => setView("settings")}><span>⚙</span>账号安全</button></nav><div className="sidebar-bottom"><div className="account-card"><span className="avatar">{user.display_name.slice(0, 1)}</span><span><strong>{user.display_name}</strong><small>{user.workspace_name}</small></span><button onClick={logout} title="退出登录">退出</button></div></div></aside>
    <section className="workspace">{user.must_change_password && view !== "settings" && <button className="password-alert" onClick={() => setView("settings")}>首次登录请尽快修改临时密码 →</button>}{error && <p className="notice-bar">{error}</p>}{view === "overview" && dashboard && <DashboardView dashboard={dashboard} startDate={startDate} onStartDate={setStartDate} onEdit={setDialog} onNew={() => setDialog("new")} />}{view === "connections" && <Connections />}{view === "settings" && <div className="settings-page"><div className="page-heading"><p className="eyebrow">个人设置</p><h1>账号与安全</h1></div><PasswordPanel onChanged={setUser} /><button className="ghost-button mobile-logout" onClick={logout}>退出登录</button></div>}
      <nav className="mobile-nav"><button className={view === "overview" ? "active" : ""} onClick={() => setView("overview")}><span>⌂</span>房态</button><button className={view === "connections" ? "active" : ""} onClick={() => setView("connections")}><span>↗</span>连接</button><button className="mobile-add" onClick={() => setDialog("new")} aria-label="新建事件">＋</button><button className={view === "settings" ? "active" : ""} onClick={() => setView("settings")}><span>⚙</span>安全</button><button onClick={logout}><span>⇥</span>退出</button></nav></section>
    {dialog && dashboard && <EventDialog rooms={dashboard.rooms} event={dialog === "new" ? null : dialog} startDate={startDate} onClose={() => setDialog(null)} onSaved={loadDashboard} />}
  </main>;
}
