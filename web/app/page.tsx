"use client";

import { FormEvent, PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

type User = { id: string; email: string; display_name: string; job_title: string; role: string; workspace_id: string; workspace_name: string; timezone: string; must_change_password: boolean; onboarding_completed: boolean };
type Room = { id: string; code: string; room_type: string; floor: string };
type RoomDraft = { code: string; room_type: string; floor: string };
type HotelEvent = { id: string; room_id: string | null; title: string; guest_name: string; event_type: string; status: string; start_date: string; end_date: string; notes: string; source_system: string; sync_status: string };
type Dashboard = { workspace_name: string; timezone: string; rooms: Room[]; events: HotelEvent[]; unassigned_count: number };
type SyncMode = "two_way" | "read_only" | "write_only" | "disabled";
type Connection = { provider: "google" | "microsoft"; configured: boolean; configuration_issue: string | null; redirect_uri: string; status: string; account_email: string | null; selected_calendar_id: string | null; selected_calendar_name: string | null; sync_mode: SyncMode; sync_label: string; last_sync_at: string | null; last_error: string | null };
type Calendar = { id: string; name: string; primary: boolean };
type TimelineScale = "day" | "week";
type DragMode = "move" | "start" | "end";
type AppView = "overview" | "connections" | "settings";
type OAuthResult = "" | "connected" | "denied";

const PENDING_GOOGLE_CALENDAR = "auto-calendar.pending-google-calendar";

const TIMEZONES = [
  ["Asia/Shanghai", "中国标准时间（广州 / 上海）"],
  ["America/Los_Angeles", "美国太平洋时间"],
  ["America/New_York", "美国东部时间"],
  ["Europe/London", "英国时间"],
  ["Asia/Tokyo", "日本时间"],
] as const;

const OAUTH_SETUP = {
  google: {
    name: "Google Calendar",
    consoleUrl: "https://console.cloud.google.com/auth/clients",
    envNames: "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET",
  },
  microsoft: {
    name: "Microsoft 365",
    consoleUrl: "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade",
    envNames: "MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET",
  },
} as const;

const isLocalAddress = (value: string) => value.startsWith("http://localhost:") || value.startsWith("http://127.0.0.1:");

function OAuthDeploymentGuide({ connections }: { connections: Connection[] }) {
  if (!connections.length) return null;
  const callback = connections[0].redirect_uri;
  const localOnly = isLocalAddress(callback);
  const baseUrl = callback.split("/api/oauth/")[0];
  return <section className={`oauth-guide-entry ${localOnly ? "local-only" : "public-ready"}`}>
    <div>
      <span>{localOnly ? "当前使用 localhost · 适合本机测试" : "当前使用公网 HTTPS 回调"}</span>
      <h2>第一次配置？按图完成 Google / Microsoft OAuth</h2>
      <p>{localOnly ? "localhost 在同一台电脑上可以正常授权；迁移到 VPS 或异地访问时再换成固定公网 HTTPS 域名。" : `当前应用入口为 ${baseUrl}，供应商后台登记的 callback 必须与本页逐字一致。`}</p>
    </div>
    <a href="/oauth-guide">打开完整图文教程 <b>→</b></a>
  </section>;
}

const api = async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
  const response = await fetch(path, { ...options, credentials: "include", headers: { "Content-Type": "application/json", ...options.headers } });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "请求失败" }));
    const detail = Array.isArray(payload.detail) ? payload.detail.map((item: { msg?: string }) => item.msg || "输入无效").join("；") : payload.detail;
    throw new Error(detail || `请求失败 (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
};
const iso = (value: Date) => [value.getFullYear(), String(value.getMonth() + 1).padStart(2, "0"), String(value.getDate()).padStart(2, "0")].join("-");
const parseIso = (value: string) => { const [year, month, day] = value.split("-").map(Number); return new Date(year, month - 1, day); };
const addDays = (value: Date, days: number) => { const result = new Date(value); result.setDate(result.getDate() + days); return result; };
const diffDays = (left: Date, right: Date) => Math.round((left.getTime() - right.getTime()) / 86_400_000);
const today = (timeZone = "Asia/Shanghai") => {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const number = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
  return new Date(number("year"), number("month") - 1, number("day"));
};
const dateLabel = (value: Date) => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(value);
const initialNavigation = (): { view: AppView; notice: string; error: string; oauthResult: OAuthResult; shouldCleanUrl: boolean } => {
  if (typeof window === "undefined") return { view: "overview", notice: "", error: "", oauthResult: "", shouldCleanUrl: false };
  const params = new URLSearchParams(window.location.search);
  const requestedView = params.get("view");
  const oauthResult = params.get("oauth");
  const view: AppView = oauthResult || requestedView === "connections" ? "connections" : requestedView === "settings" ? "settings" : "overview";
  return {
    view,
    notice: oauthResult === "connected" ? "日历账号授权成功，请选择需要同步的日历。" : "",
    error: oauthResult === "denied" ? "日历授权未完成。请检查账号类型、测试用户和回调地址；完整排错步骤见图文教程。" : "",
    oauthResult: oauthResult === "connected" || oauthResult === "denied" ? oauthResult : "",
    shouldCleanUrl: Boolean(requestedView || oauthResult),
  };
};

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
    <section className="login-story"><div className="login-brand"><span>A</span><strong>Auto Calendar</strong></div><div><p className="eyebrow light">为小型酒店设计的日历中台</p><h1>把分散的预订日历，<br />变成一张清楚的房态图。</h1><p>Google Calendar、Microsoft 365 与酒店房间在同一条时间轴上协作。</p></div><div className="trust-row"><span>本地数据</span><span>加密凭据</span><span>响应式 PWA</span></div></section>
    <section className="login-panel"><form className="login-card" onSubmit={submit}><div className="mobile-brand"><span>A</span><strong>Auto Calendar</strong></div><p className="eyebrow">酒店运营工作台</p><h2>登录账号</h2><p className="form-intro">账号登录始终是必需的；局域网和 ZeroTier 只改变网络入口，不会绕过应用账号。</p><label>邮箱<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label><label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required minLength={8} /></label>{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button login-button" disabled={loading}>{loading ? "正在登录…" : "安全登录"}</button><p className="login-help">首次运行的临时密码保存在服务器 <code>.env</code> 中。</p></form></section>
  </main>;
}

function Onboarding({ user, onComplete }: { user: User; onComplete: (user: User) => void }) {
  const [displayName, setDisplayName] = useState(user.display_name === "管理员" ? "" : user.display_name);
  const [jobTitle, setJobTitle] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [timezone, setTimezone] = useState(user.timezone || "Asia/Shanghai");
  const [rooms, setRooms] = useState<RoomDraft[]>([{ code: "", room_type: "标准房", floor: "" }]);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const changeRoom = (index: number, key: keyof RoomDraft, value: string) => setRooms((current) => current.map((room, roomIndex) => roomIndex === index ? { ...room, [key]: value } : room));
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(""); setLoading(true);
    try { onComplete(await api<User>("/api/settings/onboarding", { method: "POST", body: JSON.stringify({ display_name: displayName, job_title: jobTitle, workspace_name: workspaceName, timezone, rooms }) })); }
    catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  return <main className="onboarding-shell"><section className="onboarding-card">
    <div className="onboarding-copy"><div className="login-brand"><span>A</span><strong>Auto Calendar</strong></div><p className="eyebrow light">首次登录设置</p><h1>这次由你定义酒店，<br />系统不再替你假设。</h1><p>填写真实姓名、展示身份和酒店资料。你的系统权限仍然是工作区管理员，展示身份只用于界面和协作。</p><div className="role-explainer"><strong>系统权限</strong><span>工作区管理员 · 可管理酒店、房间、日历连接与账号安全</span></div></div>
    <form className="onboarding-form" onSubmit={submit}>
      <div><p className="step-label">01 · 管理员身份</p><h2>你是谁？</h2></div><div className="form-grid"><label>姓名<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="例如：陈先生" required /></label><label>展示身份<input value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} placeholder="例如：业主、总经理" required /></label></div>
      <div><p className="step-label">02 · 酒店资料</p><h2>你要管理哪家酒店？</h2></div><div className="form-grid"><label>酒店名称<input value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} placeholder="请输入真实酒店名称" required /></label><label>业务时区<select value={timezone} onChange={(event) => setTimezone(event.target.value)}>{TIMEZONES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
      <div className="room-setup-heading"><div><p className="step-label">03 · 房间</p><h2>先添加至少一个房间</h2></div><button type="button" className="ghost-button" onClick={() => setRooms((current) => [...current, { code: "", room_type: "标准房", floor: "" }])}>＋ 添加房间</button></div>
      <div className="room-setup-list">{rooms.map((room, index) => <div className="room-setup-row" key={index}><label>房号<input value={room.code} onChange={(event) => changeRoom(index, "code", event.target.value)} placeholder="301" required /></label><label>房型<input value={room.room_type} onChange={(event) => changeRoom(index, "room_type", event.target.value)} required /></label><label>楼层<input value={room.floor} onChange={(event) => changeRoom(index, "floor", event.target.value)} placeholder="3F" /></label><button type="button" className="remove-room" aria-label="移除此房间" disabled={rooms.length === 1} onClick={() => setRooms((current) => current.filter((_, roomIndex) => roomIndex !== index))}>×</button></div>)}</div>
      {error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button onboarding-submit" disabled={loading}>{loading ? "正在创建工作区…" : "进入酒店工作台"}</button>
    </form>
  </section></main>;
}

function PasswordPanel({ onChanged }: { onChanged: (user: User) => void }) {
  const [currentPassword, setCurrentPassword] = useState(""); const [newPassword, setNewPassword] = useState(""); const [message, setMessage] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); setMessage(""); try { const changed = await api<User>("/api/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }); onChanged(changed); setCurrentPassword(""); setNewPassword(""); setMessage("密码已更新"); } catch (reason) { setMessage((reason as Error).message); } };
  return <section className="settings-card"><div><p className="eyebrow">账号安全</p><h2>修改登录密码</h2><p>建议使用 12 位以上、只在本系统使用的密码。</p></div><form onSubmit={submit}><label>当前密码<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required /></label><label>新密码<input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" minLength={12} required /></label>{message && <p className={message === "密码已更新" ? "form-success" : "form-error"}>{message}</p>}<button className="primary-button text-button">保存新密码</button></form></section>;
}

function SettingsPage({ user, rooms, onUser, onRoomsChanged, onLogout }: { user: User; rooms: Room[]; onUser: (user: User) => void; onRoomsChanged: () => void; onLogout: () => void }) {
  const [profile, setProfile] = useState({ display_name: user.display_name, job_title: user.job_title });
  const [workspace, setWorkspace] = useState({ workspace_name: user.workspace_name, timezone: user.timezone });
  const [roomDraft, setRoomDraft] = useState<RoomDraft>({ code: "", room_type: "标准房", floor: "" });
  const [editingRoom, setEditingRoom] = useState<Room | null>(null); const [message, setMessage] = useState("");
  const saveProfile = async (event: FormEvent) => { event.preventDefault(); setMessage(""); try { onUser(await api<User>("/api/settings/profile", { method: "PATCH", body: JSON.stringify(profile) })); setMessage("个人资料已保存"); } catch (reason) { setMessage((reason as Error).message); } };
  const saveWorkspace = async (event: FormEvent) => { event.preventDefault(); setMessage(""); try { onUser(await api<User>("/api/settings/workspace", { method: "PATCH", body: JSON.stringify(workspace) })); setMessage("酒店资料已保存"); } catch (reason) { setMessage((reason as Error).message); } };
  const saveRoom = async (event: FormEvent) => { event.preventDefault(); setMessage(""); try { await api(editingRoom ? `/api/rooms/${editingRoom.id}` : "/api/rooms", { method: editingRoom ? "PATCH" : "POST", body: JSON.stringify(roomDraft) }); const wasEditing = Boolean(editingRoom); setRoomDraft({ code: "", room_type: "标准房", floor: "" }); setEditingRoom(null); await onRoomsChanged(); setMessage(wasEditing ? "房间已更新" : "房间已添加"); } catch (reason) { setMessage((reason as Error).message); } };
  const removeRoom = async (room: Room) => { if (!window.confirm(`确认移除房间 ${room.code}？关联事件会进入待分配区。`)) return; try { await api(`/api/rooms/${room.id}`, { method: "DELETE" }); await onRoomsChanged(); setMessage(`房间 ${room.code} 已移除`); } catch (reason) { setMessage((reason as Error).message); } };
  const beginEdit = (room: Room) => { setEditingRoom(room); setRoomDraft({ code: room.code, room_type: room.room_type, floor: room.floor }); };
  return <section className="settings-page">
    <div className="page-heading"><div><p className="eyebrow">管理中心</p><h1>账号与酒店设置</h1><p>展示身份用于界面说明；系统权限角色由账号体系控制，不会随职位名称改变。</p></div></div>{message && <p className={message.includes("已") ? "notice-bar success" : "notice-bar"}>{message}</p>}
    <section className="settings-card"><div><p className="eyebrow">个人资料</p><h2>身份与姓名</h2><p>当前系统权限：<strong>工作区管理员</strong>。邮箱账号为 {user.email}。</p></div><form onSubmit={saveProfile}><label>姓名<input value={profile.display_name} onChange={(event) => setProfile({ ...profile, display_name: event.target.value })} required /></label><label>展示身份<input value={profile.job_title} onChange={(event) => setProfile({ ...profile, job_title: event.target.value })} placeholder="业主、总经理、运营负责人…" required /></label><button className="primary-button text-button">保存个人资料</button></form></section>
    <section className="settings-card"><div><p className="eyebrow">酒店工作区</p><h2>酒店名称与时区</h2><p>时区会影响“今天”、入住日期和外部日历同步的解释方式。</p></div><form onSubmit={saveWorkspace}><label>酒店名称<input value={workspace.workspace_name} onChange={(event) => setWorkspace({ ...workspace, workspace_name: event.target.value })} required /></label><label>业务时区<select value={workspace.timezone} onChange={(event) => setWorkspace({ ...workspace, timezone: event.target.value })}>{TIMEZONES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className="primary-button text-button">保存酒店资料</button></form></section>
    <section className="room-management settings-card"><div><p className="eyebrow">酒店资源</p><h2>房间管理</h2><p>移除房间不会删除事件，原事件会安全地进入待分配区。</p></div><div><div className="room-list">{rooms.map((room) => <div className="room-list-item" key={room.id}><span><strong>{room.code}</strong><small>{room.room_type}{room.floor ? ` · ${room.floor}` : ""}</small></span><span><button type="button" onClick={() => beginEdit(room)}>编辑</button><button type="button" className="danger-link" onClick={() => removeRoom(room)}>移除</button></span></div>)}{!rooms.length && <p className="empty-note">暂无房间，请先添加一个房间。</p>}</div><form className="room-editor" onSubmit={saveRoom}><strong>{editingRoom ? `编辑 ${editingRoom.code}` : "添加房间"}</strong><div className="room-editor-grid"><label>房号<input value={roomDraft.code} onChange={(event) => setRoomDraft({ ...roomDraft, code: event.target.value })} required /></label><label>房型<input value={roomDraft.room_type} onChange={(event) => setRoomDraft({ ...roomDraft, room_type: event.target.value })} required /></label><label>楼层<input value={roomDraft.floor} onChange={(event) => setRoomDraft({ ...roomDraft, floor: event.target.value })} /></label></div><div className="inline-actions">{editingRoom && <button type="button" className="ghost-button" onClick={() => { setEditingRoom(null); setRoomDraft({ code: "", room_type: "标准房", floor: "" }); }}>取消编辑</button>}<button className="primary-button text-button">{editingRoom ? "保存房间" : "添加房间"}</button></div></form></div></section>
    <PasswordPanel onChanged={onUser} /><button className="mobile-logout danger-button" onClick={onLogout}>退出当前账号</button>
  </section>;
}

function Connections({ oauthResult }: { oauthResult: OAuthResult }) {
  const [items, setItems] = useState<Connection[]>([]); const [calendars, setCalendars] = useState<Record<string, Calendar[]>>({}); const [calendarNames, setCalendarNames] = useState<Record<string, string>>({ google: "Auto Calendar · 酒店订房", microsoft: "Auto Calendar · 酒店订房" }); const [message, setMessage] = useState(""); const [copied, setCopied] = useState<string | null>(null); const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => api<Connection[]>("/api/connections").then((connections) => { setItems(connections); setCalendarNames((current) => ({ ...current, ...Object.fromEntries(connections.filter((item) => item.selected_calendar_name).map((item) => [item.provider, item.selected_calendar_name!])) })); }).catch((error) => setMessage(error.message)), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (oauthResult !== "connected") return;
    const pendingName = window.sessionStorage.getItem(PENDING_GOOGLE_CALENDAR);
    if (!pendingName) return;
    window.sessionStorage.removeItem(PENDING_GOOGLE_CALENDAR);
    setCalendarNames((current) => ({ ...current, google: pendingName }));
    setBusy("create-google");
    setMessage("Google 已补充授权，正在继续创建刚才的专用日历…");
    api("/api/connections/google/calendars", { method: "POST", body: JSON.stringify({ calendar_name: pendingName }) })
      .then(async () => {
        const available = await api<Calendar[]>("/api/connections/google/calendars");
        setCalendars((current) => ({ ...current, google: available }));
        await load();
        setMessage(`已在 Google 创建并选中专用日历“${pendingName}”`);
      })
      .catch((reason) => setMessage(`Google 已重新授权，但自动创建仍未完成：${(reason as Error).message}`))
      .finally(() => setBusy(null));
  }, [load, oauthResult]);
  const connect = async (provider: string) => { try { const result = await api<{ authorization_url: string }>(`/api/oauth/${provider}/start`, { method: "POST" }); window.location.assign(result.authorization_url); } catch (reason) { setMessage((reason as Error).message); } };
  const getCalendars = async (provider: string) => { try { const available = await api<Calendar[]>(`/api/connections/${provider}/calendars`); setCalendars((current) => ({ ...current, [provider]: available })); } catch (reason) { setMessage((reason as Error).message); } };
  const saveSettings = async (provider: string, changes: Partial<{ calendar_id: string; calendar_name: string; sync_mode: SyncMode; sync_label: string }> = {}) => { const current = items.find((item) => item.provider === provider); if (!current) return; const calendarId = changes.calendar_id || current.selected_calendar_id; const calendarName = changes.calendar_name || current.selected_calendar_name; if (!calendarId || !calendarName) { setMessage("请先选择或创建专用日历"); return; } try { await api(`/api/connections/${provider}/settings`, { method: "PUT", body: JSON.stringify({ calendar_id: calendarId, calendar_name: calendarName, sync_mode: changes.sync_mode || current.sync_mode, sync_label: changes.sync_label || current.sync_label }) }); await load(); setMessage("同步设置已保存"); } catch (reason) { setMessage((reason as Error).message); } };
  const selectCalendar = async (provider: string, value: string) => { const item = calendars[provider]?.find((calendar) => calendar.id === value); if (item) await saveSettings(provider, { calendar_id: item.id, calendar_name: item.name }); };
  const createDedicated = async (provider: string) => { const name = calendarNames[provider]?.trim(); if (!name) { setMessage("请输入专用日历名称"); return; } setBusy(`create-${provider}`); try { await api(`/api/connections/${provider}/calendars`, { method: "POST", body: JSON.stringify({ calendar_name: name }) }); await getCalendars(provider); await load(); setMessage(`已在 ${provider === "google" ? "Google" : "Microsoft"} 创建并选中专用日历“${name}”`); } catch (reason) { const detail = (reason as Error).message; if (provider === "google" && /insufficient authentication scopes|旧授权需点击/.test(detail)) { window.sessionStorage.setItem(PENDING_GOOGLE_CALENDAR, name); setMessage("Google 旧授权缺少创建日历权限，正在打开补充授权；完成后会自动继续创建。"); await connect("google"); } else { setMessage(detail); } } finally { setBusy(null); } };
  const sync = async (provider: string) => { setBusy(`sync-${provider}`); try { const result = await api<{ synced: number }>(`/api/connections/${provider}/sync`, { method: "POST" }); setMessage(`同步完成：处理 ${result.synced} 条读取或写入变更`); await load(); } catch (reason) { setMessage((reason as Error).message); } finally { setBusy(null); } };
  const syncAll = async () => { setBusy("sync-all"); try { const result = await api<{ synced: Record<string, number>; errors: Record<string, string> }>("/api/connections/sync-all", { method: "POST" }); const total = Object.values(result.synced).reduce((sum, value) => sum + value, 0); const errors = Object.entries(result.errors).map(([provider, detail]) => `${provider}: ${detail}`).join("；"); setMessage(errors ? `已处理 ${total} 条变更；${errors}` : `Google、Microsoft 与 Auto Calendar 已完成一轮同步，共处理 ${total} 条变更`); await load(); } catch (reason) { setMessage((reason as Error).message); } finally { setBusy(null); } };
  const copyCallback = async (item: Connection) => { try { await navigator.clipboard.writeText(item.redirect_uri); setCopied(item.provider); window.setTimeout(() => setCopied(null), 1800); } catch { setMessage("浏览器未允许自动复制，请手动选择回调地址复制。"); } };
  return <section className="connections-page">
    <div className="page-heading connection-heading"><div><p className="eyebrow">外部日历</p><h1>让三端使用同一份酒店日程</h1><p>Auto Calendar 负责同步；Google / Outlook 的专用日历负责隔离酒店事件。相同名称的 tag 只是标识，不会自行产生同步。</p></div><button className="primary-button text-button" onClick={syncAll} disabled={busy === "sync-all" || !items.some((item) => item.selected_calendar_id)}>{busy === "sync-all" ? "正在同步…" : "同步全部日历"}</button></div>
    <OAuthDeploymentGuide connections={items} />
    {message && <p className="notice-bar">{message}</p>}
    <div className="connection-grid">{items.map((item) => {
      const setup = OAUTH_SETUP[item.provider];
      return <article className="connection-card" key={item.provider}>
        <div className={`provider-logo ${item.provider}`}>{item.provider === "google" ? "G" : "M"}</div>
        <div className="connection-title"><h2>{setup.name}</h2><span className={`status ${item.status}`}>{item.status === "connected" ? "已连接" : "未连接"}</span></div>
        <p>{item.account_email || (item.configured ? "应用凭据已就绪，可以授权你自己的日历账号。" : item.configuration_issue)}</p>
        {item.selected_calendar_name && <p className="selected-calendar">同步日历：{item.selected_calendar_name}</p>}
        {item.last_error && <p className="connection-error">最近错误：{item.last_error}</p>}
        {!item.configured && <div className="oauth-setup-guide">
          <p>需要在供应商后台创建 Web OAuth 应用，再把生成的 <code>{setup.envNames}</code> 写入服务器。</p>
          <div className="callback-copy"><code>{item.redirect_uri}</code><button type="button" onClick={() => copyCallback(item)}>{copied === item.provider ? "已复制" : "复制 callback"}</button></div>
          <div className="setup-links"><a href={`/oauth-guide#${item.provider}`}>查看图文教程</a><a href={setup.consoleUrl} target="_blank" rel="noreferrer">打开官方控制台 ↗</a></div>
        </div>}
        {item.status === "connected" ? <div className="sync-settings">
          <div className="dedicated-calendar"><label>专用日历名称<input value={calendarNames[item.provider] || ""} onChange={(event) => setCalendarNames((current) => ({ ...current, [item.provider]: event.target.value }))} /></label><button className="ghost-button" onClick={() => createDedicated(item.provider)} disabled={busy === `create-${item.provider}`}>{busy === `create-${item.provider}` ? "创建中…" : "创建专用日历"}</button><small>直接创建到当前已授权的 {item.provider === "google" ? "Google Calendar" : "Outlook / Microsoft 365"} 账号，并自动设为同步目标。</small></div>
          <div className="connection-actions"><button className="ghost-button" onClick={() => getCalendars(item.provider)}>选择已有日历</button><button className="primary-button text-button" onClick={() => sync(item.provider)} disabled={!item.selected_calendar_id || busy === `sync-${item.provider}`}>{busy === `sync-${item.provider}` ? "同步中…" : "立即同步"}</button></div>
          {calendars[item.provider] && <label>同步范围<select value={item.selected_calendar_id || ""} onChange={(event) => selectCalendar(item.provider, event.target.value)}><option value="">请选择一个日历</option>{calendars[item.provider].map((calendar) => <option value={calendar.id} key={calendar.id}>{calendar.name}{calendar.primary ? "（主日历）" : ""}</option>)}</select></label>}
          <div className="sync-option-grid"><label>同步方向<select value={item.sync_mode} onChange={(event) => saveSettings(item.provider, { sync_mode: event.target.value as SyncMode })}><option value="two_way">双向同步（推荐）</option><option value="read_only">只读入 Auto Calendar</option><option value="write_only">只写到外部日历</option><option value="disabled">暂停同步</option></select></label><label>分类 / 标识<input value={item.sync_label} onChange={(event) => setItems((current) => current.map((connection) => connection.provider === item.provider ? { ...connection, sync_label: event.target.value } : connection))} onBlur={() => saveSettings(item.provider, { sync_label: item.sync_label })} /></label></div>
          <div className="reauthorize-row"><span>{item.last_sync_at ? `上次同步：${new Date(item.last_sync_at).toLocaleString("zh-CN")}` : "尚未执行同步"}</span><button onClick={() => connect(item.provider)}>{item.provider === "google" ? "重新授权 Google" : "重新授权 Microsoft"}</button></div>
        </div> : <button className="primary-button wide text-button" disabled={!item.configured} onClick={() => connect(item.provider)}>{item.configured ? `授权我的 ${setup.name}` : "完成上面配置后即可授权"}</button>}
      </article>;
    })}</div>
    <article className="architecture-note"><strong>三端同步链路</strong><span>任一端修改 → Auto Calendar 按事件映射识别同一条记录 → 写入另一个专用日历。Google 使用隐藏扩展属性标识，Outlook 同时显示分类；真正的对应关系保存在服务端数据库中。</span></article>
  </section>;
}

function EventDialog({ rooms, event, startDate, onClose, onSaved }: { rooms: Room[]; event?: HotelEvent | null; startDate: Date; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ room_id: event?.room_id || "", title: event?.title || "", guest_name: event?.guest_name || "", event_type: event?.event_type || "reservation", status: event?.status || "reserved", start_date: event?.start_date || iso(startDate), end_date: event?.end_date || iso(addDays(startDate, 1)), notes: event?.notes || "" }); const [error, setError] = useState("");
  const set = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async (submitEvent: FormEvent) => { submitEvent.preventDefault(); setError(""); try { await api(event ? `/api/events/${event.id}` : "/api/events", { method: event ? "PATCH" : "POST", body: JSON.stringify({ ...form, room_id: form.room_id || null }) }); onSaved(); onClose(); } catch (reason) { setError((reason as Error).message); } };
  const remove = async () => { if (!event || !window.confirm("确认删除这条事件？")) return; try { await api(`/api/events/${event.id}`, { method: "DELETE" }); onSaved(); onClose(); } catch (reason) { setError((reason as Error).message); } };
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="event-title"><div className="modal-head"><div><p className="eyebrow">房态事件</p><h2 id="event-title">{event ? "编辑事件" : "新建事件"}</h2></div><button onClick={onClose} aria-label="关闭">×</button></div><form onSubmit={submit}><label className="full">事件名称<input value={form.title} onChange={(inputEvent) => set("title", inputEvent.target.value)} placeholder="例如：王女士 · 官网预订" required /></label><label>房间<select value={form.room_id} onChange={(inputEvent) => set("room_id", inputEvent.target.value)}><option value="">暂不分配</option>{rooms.map((room) => <option value={room.id} key={room.id}>{room.code} · {room.room_type}</option>)}</select></label><label>客人姓名<input value={form.guest_name} onChange={(inputEvent) => set("guest_name", inputEvent.target.value)} /></label><label>开始日期<input type="date" value={form.start_date} onChange={(inputEvent) => set("start_date", inputEvent.target.value)} required /></label><label>结束日期<input type="date" value={form.end_date} onChange={(inputEvent) => set("end_date", inputEvent.target.value)} required /></label><label>类型<select value={form.event_type} onChange={(inputEvent) => set("event_type", inputEvent.target.value)}><option value="reservation">预订</option><option value="cleaning">清洁</option><option value="maintenance">维护</option><option value="blocked">锁房</option></select></label><label>状态<select value={form.status} onChange={(inputEvent) => set("status", inputEvent.target.value)}><option value="reserved">已预订</option><option value="checked_in">已入住</option><option value="checked_out">已退房</option><option value="cleaning">清洁中</option><option value="maintenance">维护中</option><option value="blocked">已锁房</option></select></label><label className="full">备注<textarea value={form.notes} onChange={(inputEvent) => set("notes", inputEvent.target.value)} rows={3} /></label>{error && <p className="form-error full">{error}</p>}<div className="modal-actions full">{event && <button type="button" className="danger-button" onClick={remove}>删除</button>}<span /><button type="button" className="ghost-button" onClick={onClose}>取消</button><button className="primary-button text-button">保存事件</button></div></form></section></div>;
}

function TimelineBooking({ event, viewStart, columns, unitDays, tone, onEdit, onDates }: { event: HotelEvent; viewStart: Date; columns: number; unitDays: number; tone: string; onEdit: (event: HotelEvent) => void; onDates: (eventId: string, startDate: string, endDate: string) => Promise<void> }) {
  const [preview, setPreview] = useState({ start: event.start_date, end: event.end_date });
  const drag = useRef<null | { pointerId: number; mode: DragMode; pointerX: number; cellWidth: number; start: Date; end: Date; currentStart: string; currentEnd: string; moved: boolean }>(null); const suppressClick = useRef(false);
  const position = useMemo(() => { const start = Math.max(0, Math.floor(diffDays(parseIso(preview.start), viewStart) / unitDays)); const end = Math.min(columns, Math.ceil(diffDays(parseIso(preview.end), viewStart) / unitDays)); return { gridColumn: `${start + 1} / ${Math.max(start + 2, end + 1)}` }; }, [columns, preview, unitDays, viewStart]);
  const startDrag = (pointerEvent: ReactPointerEvent<HTMLElement>, mode: DragMode) => { if (pointerEvent.pointerType === "mouse" && pointerEvent.button !== 0) return; const booking = pointerEvent.currentTarget.closest(".booking") as HTMLElement | null; const roomDays = pointerEvent.currentTarget.closest(".room-days") as HTMLElement | null; if (!booking || !roomDays) return; pointerEvent.preventDefault(); booking.setPointerCapture(pointerEvent.pointerId); drag.current = { pointerId: pointerEvent.pointerId, mode, pointerX: pointerEvent.clientX, cellWidth: roomDays.getBoundingClientRect().width / columns, start: parseIso(event.start_date), end: parseIso(event.end_date), currentStart: event.start_date, currentEnd: event.end_date, moved: false }; booking.classList.add("dragging"); };
  const moveDrag = (pointerEvent: ReactPointerEvent<HTMLDivElement>) => { const active = drag.current; if (!active || active.pointerId !== pointerEvent.pointerId) return; const units = Math.round((pointerEvent.clientX - active.pointerX) / active.cellWidth); if (!units) return; active.moved = true; const delta = units * unitDays; let start = active.start; let end = active.end; if (active.mode === "move") { start = addDays(start, delta); end = addDays(end, delta); } else if (active.mode === "start") { start = addDays(start, delta); if (start >= end) start = addDays(end, -1); } else { end = addDays(end, delta); if (end <= start) end = addDays(start, 1); } active.currentStart = iso(start); active.currentEnd = iso(end); setPreview({ start: active.currentStart, end: active.currentEnd }); };
  const finishDrag = async (pointerEvent: ReactPointerEvent<HTMLDivElement>) => { const active = drag.current; if (!active || active.pointerId !== pointerEvent.pointerId) return; pointerEvent.currentTarget.classList.remove("dragging"); drag.current = null; if (active.moved) { suppressClick.current = true; window.setTimeout(() => { suppressClick.current = false; }, 0); if (active.currentStart !== event.start_date || active.currentEnd !== event.end_date) { try { await onDates(event.id, active.currentStart, active.currentEnd); } catch { setPreview({ start: event.start_date, end: event.end_date }); } } } };
  const cancelDrag = (pointerEvent: ReactPointerEvent<HTMLDivElement>) => { pointerEvent.currentTarget.classList.remove("dragging"); drag.current = null; setPreview({ start: event.start_date, end: event.end_date }); };
  return <div className={`booking booking-${tone}`} style={position} onPointerMove={moveDrag} onPointerUp={finishDrag} onPointerCancel={cancelDrag}><button type="button" className="resize-handle resize-start" aria-label={`调整 ${event.title} 开始日期`} onPointerDown={(pointerEvent) => startDrag(pointerEvent, "start")} /><button type="button" className="booking-body" onPointerDown={(pointerEvent) => startDrag(pointerEvent, "move")} onClick={() => { if (!suppressClick.current) onEdit(event); }}><b>{event.title}</b><small>{preview.start.slice(5)} → {preview.end.slice(5)}</small></button><button type="button" className="resize-handle resize-end" aria-label={`调整 ${event.title} 结束日期`} onPointerDown={(pointerEvent) => startDrag(pointerEvent, "end")} /></div>;
}

function DashboardView({ dashboard, startDate, scale, onStartDate, onScale, onEdit, onNew, onEventDates, onOpenSettings }: { dashboard: Dashboard; startDate: Date; scale: TimelineScale; onStartDate: (date: Date) => void; onScale: (scale: TimelineScale) => void; onEdit: (event: HotelEvent) => void; onNew: () => void; onEventDates: (eventId: string, startDate: string, endDate: string) => Promise<void>; onOpenSettings: () => void }) {
  const columns = scale === "day" ? 7 : 6; const unitDays = scale === "day" ? 1 : 7; const windowDays = columns * unitDays;
  const dates = useMemo(() => Array.from({ length: columns }, (_, index) => addDays(startDate, index * unitDays)), [columns, startDate, unitDays]); const current = iso(today(dashboard.timezone));
  const dayEvents = dashboard.events.filter((event) => event.start_date <= current && event.end_date > current); const occupancy = dashboard.rooms.length ? Math.round(dayEvents.filter((event) => event.status === "checked_in" || event.status === "reserved").length / dashboard.rooms.length * 100) : 0;
  const tone = (event: HotelEvent) => event.status === "checked_in" ? "mint" : event.event_type === "cleaning" ? "amber" : event.event_type === "maintenance" || event.event_type === "blocked" ? "rose" : event.source_system === "microsoft" ? "violet" : "blue";
  return <><header className="topbar"><div><p className="eyebrow">{dateLabel(today(dashboard.timezone))}</p><h1>房态总览</h1></div><div className="top-actions"><button className="primary-button" onClick={onNew}><span>＋</span><b>新建事件</b></button></div></header>
    <section className="metrics"><article className="metric-card accent-blue"><p>今日在店</p><strong>{dayEvents.filter((event) => event.status === "checked_in").length}</strong><span>已办理入住</span></article><article className="metric-card accent-green"><p>今日有安排</p><strong>{dayEvents.length}</strong><span>预订、清洁与维护</span></article><article className="metric-card accent-orange"><p>房间占用率</p><strong>{occupancy}%</strong><span>按今日房态估算</span></article><article className="metric-card accent-red"><p>待分配</p><strong>{dashboard.unassigned_count}</strong><span>外部日历或原房间已移除</span></article></section>
    {dashboard.unassigned_count > 0 && <div className="unassigned-banner"><span><strong>{dashboard.unassigned_count} 条事件等待分配房间</strong><small>外部日历事件不会自动占用房间，避免误配。</small></span></div>}
    <section className="timeline-card"><div className="timeline-toolbar"><div><div className="section-title-row"><h2>房间时间轴</h2><span className="live-pill"><i />数据已保存</span></div><p>{dashboard.workspace_name} · {scale === "day" ? "按日查看 7 天" : "按周查看 6 周"}</p></div><div className="toolbar-cluster"><div className="scale-switch" aria-label="时间轴单位"><button className={scale === "day" ? "active" : ""} onClick={() => onScale("day")}>日</button><button className={scale === "week" ? "active" : ""} onClick={() => onScale("week")}>周</button></div><div className="toolbar-actions"><button className="ghost-button" onClick={() => onStartDate(today(dashboard.timezone))}>今天</button><div className="segment"><button aria-label="上一时间段" onClick={() => onStartDate(addDays(startDate, -windowDays))}>‹</button><button aria-label="下一时间段" onClick={() => onStartDate(addDays(startDate, windowDays))}>›</button></div></div></div></div><p className="drag-help">拖住事件中间可移动日期，拖住左右边缘可调整时长；手机和平板同样支持横向拖动。</p>
      {dashboard.rooms.length ? <div className="timeline-scroll" role="region" aria-label="房间占用时间轴"><div className="timeline-grid"><div className="room-heading">房间</div><div className="date-headings" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>{dates.map((date) => <div className={scale === "day" && iso(date) === current ? "today" : ""} key={iso(date)}><span>{scale === "day" ? new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(date) : `${date.getMonth() + 1}月${date.getDate()}日`}</span><strong>{scale === "day" ? date.getDate() : `第 ${Math.ceil(date.getDate() / 7)} 周`}</strong></div>)}</div>{dashboard.rooms.map((room) => <div className="room-row" key={room.id}><div className="room-label"><strong>{room.code}</strong><span>{room.room_type}{room.floor ? ` · ${room.floor}` : ""}</span></div><div className="room-days" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>{dates.map((date) => <span key={iso(date)} />)}{dashboard.events.filter((event) => event.room_id === room.id && event.start_date < iso(addDays(startDate, windowDays)) && event.end_date > iso(startDate)).map((event) => <TimelineBooking event={event} viewStart={startDate} columns={columns} unitDays={unitDays} tone={tone(event)} onEdit={onEdit} onDates={onEventDates} key={`${event.id}:${event.start_date}:${event.end_date}`} />)}</div></div>)}</div></div> : <div className="empty-timeline"><strong>还没有房间</strong><p>请先在设置中添加房间，再开始安排事件。</p><button className="primary-button text-button" onClick={onOpenSettings}>前往房间设置</button></div>}
      <div className="timeline-legend"><span><i className="legend-mint" />已入住</span><span><i className="legend-blue" />已预订</span><span><i className="legend-amber" />清洁</span><span><i className="legend-rose" />维护 / 锁房</span></div></section>
  </>;
}

export default function Home() {
  const [navigation] = useState(initialNavigation); const [user, setUser] = useState<User | null | undefined>(undefined); const [dashboard, setDashboard] = useState<Dashboard | null>(null); const [view, setView] = useState<AppView>(navigation.view); const [scale, setScale] = useState<TimelineScale>("day"); const [startDate, setStartDate] = useState(today()); const [dialog, setDialog] = useState<HotelEvent | null | "new">(null); const [error, setError] = useState(navigation.error); const [notice] = useState(navigation.notice);
  const loadDashboard = useCallback(async () => { try { setDashboard(await api<Dashboard>(`/api/dashboard?start=${iso(startDate)}&days=${scale === "day" ? 14 : 56}`)); setError(""); } catch (reason) { setError((reason as Error).message); } }, [scale, startDate]);
  useEffect(() => { if (navigation.shouldCleanUrl) window.history.replaceState({}, "", "/"); }, [navigation.shouldCleanUrl]);
  useEffect(() => { api<User>("/api/auth/me").then((current) => { setUser(current); setStartDate(today(current.timezone)); }).catch(() => setUser(null)); }, []);
  useEffect(() => {
    if (!user?.onboarding_completed) return;
    api<Dashboard>(`/api/dashboard?start=${iso(startDate)}&days=${scale === "day" ? 14 : 56}`)
      .then((data) => { setDashboard(data); setError(""); })
      .catch((reason) => setError((reason as Error).message));
  }, [user?.onboarding_completed, startDate, scale]);
  const updateUser = (updated: User) => { const timezoneChanged = user?.timezone !== updated.timezone; setUser(updated); if (timezoneChanged) setStartDate(today(updated.timezone)); };
  const logout = async () => { await api("/api/auth/logout", { method: "POST" }); setUser(null); setDashboard(null); };
  const updateEventDates = async (eventId: string, eventStart: string, eventEnd: string) => { try { await api(`/api/events/${eventId}`, { method: "PATCH", body: JSON.stringify({ start_date: eventStart, end_date: eventEnd }) }); await loadDashboard(); } catch (reason) { setError((reason as Error).message); throw reason; } };
  if (user === undefined) return <main className="loading-screen"><span>A</span><p>正在打开酒店工作台…</p></main>;
  if (!user) return <Login onLogin={(loggedIn) => { setUser(loggedIn); setStartDate(today(loggedIn.timezone)); }} />;
  if (!user.onboarding_completed) return <Onboarding user={user} onComplete={(completed) => { updateUser(completed); setView("overview"); }} />;
  return <main className="app-shell"><aside className="sidebar"><div className="brand-mark"><span className="brand-symbol">A</span><span><strong>Auto Calendar</strong><small>酒店运营中心</small></span></div><nav className="main-nav"><button className={`nav-item ${view === "overview" ? "active" : ""}`} onClick={() => setView("overview")}><span>⌂</span>房态总览</button><button className={`nav-item ${view === "connections" ? "active" : ""}`} onClick={() => setView("connections")}><span>↗</span>日历连接</button><button className={`nav-item ${view === "settings" ? "active" : ""}`} onClick={() => setView("settings")}><span>⚙</span>账号与酒店</button></nav><div className="sidebar-bottom"><button className="account-card" onClick={() => setView("settings")} title="打开账号与酒店设置"><span className="avatar">{user.display_name.slice(0, 1)}</span><span><strong>{user.display_name}</strong><small>{user.job_title} · {user.workspace_name}</small></span><i>›</i></button><button className="sidebar-logout" onClick={logout}>退出登录</button></div></aside>
    <section className="workspace">{user.must_change_password && view !== "settings" && <button className="password-alert" onClick={() => setView("settings")}>首次登录请尽快修改临时密码 →</button>}{notice && <p className="notice-bar success">{notice}</p>}{error && <p className="notice-bar error">{error}</p>}{view === "overview" && dashboard && <DashboardView dashboard={dashboard} startDate={startDate} scale={scale} onStartDate={setStartDate} onScale={setScale} onEdit={setDialog} onNew={() => setDialog("new")} onEventDates={updateEventDates} onOpenSettings={() => setView("settings")} />}{view === "connections" && <Connections oauthResult={navigation.oauthResult} />}{view === "settings" && <SettingsPage user={user} rooms={dashboard?.rooms || []} onUser={updateUser} onRoomsChanged={loadDashboard} onLogout={logout} />}</section>
    <nav className="mobile-nav" aria-label="移动端主导航"><button className={view === "overview" ? "active" : ""} onClick={() => setView("overview")}><span>⌂</span>房态</button><button className={view === "connections" ? "active" : ""} onClick={() => setView("connections")}><span>↗</span>连接</button><button className="mobile-add" aria-label="新建事件" onClick={() => setDialog("new")}>＋</button><button className={view === "settings" ? "active" : ""} onClick={() => setView("settings")}><span>⚙</span>设置</button></nav>
    {dialog && <EventDialog rooms={dashboard?.rooms || []} event={dialog === "new" ? null : dialog} startDate={startDate} onClose={() => setDialog(null)} onSaved={loadDashboard} />}
  </main>;
}
