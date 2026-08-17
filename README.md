# Auto Calendar

**A self-hosted hotel room-status workspace that turns Google Calendar and Microsoft 365 events into one operational timeline.**

[English](#english) · [中文](#中文)

> [!IMPORTANT]
> Auto Calendar is an early MVP and proprietary shareware. Source availability does not make it open source. See [SHAREWARE.md](SHAREWARE.md) before using or redistributing it.

---

## English

### What it is

Auto Calendar is a Docker-first calendar middleware and responsive Web UI for small hotels and lodging teams. It provides one place to:

- manage room reservations, cleaning, maintenance, and blocked dates;
- connect Google Calendar and Microsoft 365 through browser-based OAuth;
- import external calendar changes into a room-assignment workflow;
- access the same UI from desktop browsers, tablets, iPhone, and Android PWA;
- keep application data on infrastructure you control.

The MVP uses its own account/password protection on every network. LAN and ZeroTier are treated as trusted transport paths without an additional gateway login; Cloudflare Tunnel can add Cloudflare Access as a second layer for public access.

### MVP capabilities

- Responsive seven-day room timeline
- Local event create, update, soft-delete, and overlap protection
- Password login with HttpOnly server sessions and Argon2 password hashing
- Encrypted OAuth token storage using Fernet
- Google Calendar and Microsoft 365 OAuth 2.0 + PKCE connection flow
- External calendar selection, manual sync, and scheduled background sync
- Unassigned-event workflow before an imported event occupies a room
- PostgreSQL persistence and Alembic migrations
- PWA manifest and service worker
- Docker Compose deployment with an Nginx gateway
- Optional Cloudflare Tunnel container profile
- LAN and host-managed ZeroTier access
- Basic audit records for sensitive operations

### Architecture

```text
Browser / PWA
      │
      ▼
Nginx gateway :8080
      ├──────────────► Next.js responsive Web UI
      │
      └──────────────► FastAPI
                          ├── PostgreSQL
                          ├── Google Calendar API
                          └── Microsoft Graph API

Optional access paths:
LAN ───────────────► :8080
ZeroTier ──────────► :8080
Cloudflare Tunnel ─► Nginx ─► Cloudflare Access (recommended for public use)
```

### Requirements

- Docker Desktop or Docker Engine with Compose v2
- macOS, Linux, or another Docker-capable host
- A modern browser
- For calendar integration: a Google Cloud OAuth Web Application and/or a Microsoft Entra Web Application

### Quick start

```bash
git clone https://github.com/samni728/Auto-calendar.git
cd Auto-calendar
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

Open [http://localhost:8080](http://localhost:8080).

- Default administrator email: `admin@autocalendar.app`
- A random initial password is generated in the local `.env` file.
- Change the temporary password immediately after the first login.

Useful commands:

```bash
docker compose ps
docker compose logs -f api web gateway
docker compose up -d --build
docker compose down
```

`docker compose down` preserves the PostgreSQL volume. `docker compose down -v` permanently removes local database data and should only be used when intentionally resetting a test installation.

### OAuth configuration

Copy or update `.env` with credentials created in your own test projects:

```dotenv
PUBLIC_BASE_URL=https://calendar.example.com
SESSION_COOKIE_SECURE=true

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT=common
```

Register these exact redirect URIs:

- Google: `https://calendar.example.com/api/oauth/google/callback`
- Microsoft: `https://calendar.example.com/api/oauth/microsoft/callback`

OAuth consent happens in the user's browser. Client secrets and refresh tokens remain on the server; refresh tokens are encrypted before being stored in PostgreSQL. The server then refreshes access tokens and synchronizes the selected calendar on demand or at the configured interval.

Requested permissions:

- Google: identity/email, calendar-list read, calendar-event access
- Microsoft: `User.Read`, `Calendars.ReadWrite`, and `offline_access`

### Access options

#### 1. Local network

Open `http://<host-lan-ip>:8080` from another device on the same LAN. Application login remains required.

#### 2. ZeroTier

Install and join ZeroTier on the Docker host and client devices, then open `http://<host-zerotier-ip>:8080`. ZeroTier is managed on the host; the application does not need a privileged ZeroTier container. Application login remains required, while no extra Zero Trust gateway authentication is added.

#### 3. Cloudflare Tunnel

Create a remotely managed Tunnel in Cloudflare Zero Trust, point its public hostname to `http://gateway:80`, place the connector token in `.env`, and start the optional profile:

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=
```

```bash
docker compose --profile cloudflare up -d cloudflared
```

For public access, configure Cloudflare Access to allow specific Gmail, Microsoft, or other email identities. Cloudflare Access is an additional perimeter layer and does not replace the Auto Calendar account login.

The environment template reserves Account ID, API token, and hostname fields for a future automated Tunnel/DNS provisioning workflow. The MVP intentionally uses the narrower connector-token approach.

### Development and verification

Web UI:

```bash
cd web
npm install
npm run lint
npm test
```

API checks are configured through Ruff and Python compilation; the complete stack can be verified through Docker:

```bash
python3 -m compileall server/app server/alembic
docker compose config --quiet
docker compose up -d --build
curl http://localhost:8080/healthz
```

### Repository layout

```text
.
├── docs/                 Product plan and architecture decisions
├── infra/                Nginx gateway configuration
├── scripts/              Local bootstrap helpers
├── server/               FastAPI, domain models, OAuth adapters, migrations
├── web/                  Next.js responsive Web UI and PWA assets
├── docker-compose.yml    Local/self-hosted stack
├── .env.example          Configuration template without secrets
└── SHAREWARE.md          Proprietary shareware terms
```

### Current MVP boundaries

- One hotel workspace and one primary administrator workflow
- One connected account per provider per user
- Calendar changes are imported into the local timeline; complete two-way write-back and conflict reconciliation are not yet implemented
- Cloudflare Tunnel/DNS API provisioning is planned but not part of this release
- Native iOS, Android, DMG, and EXE wrappers are future packaging work; the current client is responsive Web/PWA
- This is not a PMS, booking engine, payment system, or channel manager

The longer product plan is available in [docs/plan.md](docs/plan.md).

### License

Copyright © 2026 samni728. All rights reserved.

This project is distributed as proprietary shareware, not as open-source software. Personal evaluation and non-commercial trial use are permitted under the conditions in [SHAREWARE.md](SHAREWARE.md). Commercial use, hosted service use, resale, and redistribution require prior written authorization or a separate commercial license.

---

## 中文

### 项目简介

Auto Calendar 是一个面向小型酒店和住宿团队的 Docker 自托管日历中间件与响应式 WebUI。它把酒店房间、Google Calendar 和 Microsoft 365 的事件集中到同一张运营时间轴上，用于：

- 管理预订、入住、清洁、维护和锁房事件；
- 通过浏览器 OAuth 连接 Google 与 Microsoft 日历；
- 将外部日历变化先导入待分配流程，再绑定具体房间；
- 通过桌面浏览器、Pad、iPhone 和 Android PWA 使用同一个界面；
- 将业务数据保存在自己控制的服务器或 Mac mini 上。

无论通过哪种网络访问，MVP 都保留应用自身的账号密码防护。局域网和 ZeroTier 作为可信传输路径，不额外增加网关登录；Cloudflare Tunnel 公网访问则建议叠加 Cloudflare Access，形成第二层保护。

### MVP 已有能力

- 响应式七日房态时间轴
- 本地事件新增、修改、软删除和日期冲突保护
- HttpOnly 服务端 Session 与 Argon2 密码哈希
- 使用 Fernet 加密保存 OAuth token
- Google Calendar、Microsoft 365 OAuth 2.0 + PKCE 授权流程
- 外部日历选择、手动同步和后台定时同步
- 外部事件待分配机制，避免导入后误占房间
- PostgreSQL 持久化和 Alembic 数据库迁移
- PWA manifest 与 Service Worker
- Docker Compose 和 Nginx 统一入口
- 可选的 Cloudflare Tunnel 容器 profile
- 局域网与宿主机 ZeroTier 访问
- 敏感操作的基础审计记录

### 系统架构

```text
浏览器 / PWA
      │
      ▼
Nginx 网关 :8080
      ├──────────────► Next.js 响应式 WebUI
      │
      └──────────────► FastAPI
                          ├── PostgreSQL
                          ├── Google Calendar API
                          └── Microsoft Graph API

可选访问路径：
局域网 ─────────────► :8080
ZeroTier ───────────► :8080
Cloudflare Tunnel ─► Nginx ─► Cloudflare Access（公网推荐）
```

### 运行要求

- Docker Desktop，或安装了 Compose v2 的 Docker Engine
- macOS、Linux 或其他能够运行 Docker 的主机
- 现代浏览器
- 如需日历集成：Google Cloud OAuth Web Application 和/或 Microsoft Entra Web Application

### 快速启动

```bash
git clone https://github.com/samni728/Auto-calendar.git
cd Auto-calendar
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

打开 [http://localhost:8080](http://localhost:8080)。

- 默认管理员邮箱：`admin@autocalendar.app`
- 启动脚本会在本地 `.env` 中生成随机初始密码。
- 第一次登录后请立即修改临时密码。

常用命令：

```bash
docker compose ps
docker compose logs -f api web gateway
docker compose up -d --build
docker compose down
```

`docker compose down` 不会删除 PostgreSQL 数据卷。`docker compose down -v` 会永久删除本地数据库数据，只应在明确重置测试环境时使用。

### OAuth 配置

在 `.env` 中填写自己测试项目的 OAuth 凭据：

```dotenv
PUBLIC_BASE_URL=https://calendar.example.com
SESSION_COOKIE_SECURE=true

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT=common
```

在服务商后台精确登记以下 Redirect URI：

- Google：`https://calendar.example.com/api/oauth/google/callback`
- Microsoft：`https://calendar.example.com/api/oauth/microsoft/callback`

OAuth 登录和授权在用户浏览器中完成。Client Secret 与 refresh token 只保存在服务端，refresh token 加密后写入 PostgreSQL。服务器随后可以刷新 access token，并按照配置周期或手动触发同步所选日历。

申请的主要权限：

- Google：身份/邮箱、日历列表读取和日历事件访问
- Microsoft：`User.Read`、`Calendars.ReadWrite`、`offline_access`

### 三种访问方式

#### 1. 局域网

同一局域网设备访问 `http://<主机局域网IP>:8080`。仍然需要 Auto Calendar 账号密码。

#### 2. ZeroTier

在 Docker 主机和终端设备上安装并加入同一个 ZeroTier 网络，然后访问 `http://<主机ZeroTier-IP>:8080`。ZeroTier 由宿主机维护，不需要给应用容器增加特权权限；应用账号密码继续保留，但不额外增加 Zero Trust 网关鉴权。

#### 3. Cloudflare Tunnel

在 Cloudflare Zero Trust 中创建远程管理的 Tunnel，把 Public Hostname 指向 `http://gateway:80`，将连接 token 写入 `.env`：

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=
```

启动可选 profile：

```bash
docker compose --profile cloudflare up -d cloudflared
```

公网访问建议通过 Cloudflare Access 限定 Gmail、Microsoft 或其他指定邮箱。Cloudflare Access 是应用登录之外的第二层边界防护，不能替代 Auto Calendar 自身账号密码。

环境模板已预留 Account ID、API Token 和域名参数，供后续自动创建 Tunnel/DNS 使用。MVP 暂时采用权限更窄的官方 connector token。

### 开发与验证

WebUI：

```bash
cd web
npm install
npm run lint
npm test
```

API 可以通过 Python 编译、Ruff 和完整 Docker 栈验证：

```bash
python3 -m compileall server/app server/alembic
docker compose config --quiet
docker compose up -d --build
curl http://localhost:8080/healthz
```

### 目录结构

```text
.
├── docs/                 产品规划和架构决策
├── infra/                Nginx 网关配置
├── scripts/              本地初始化脚本
├── server/               FastAPI、数据模型、OAuth adapter、数据库迁移
├── web/                  Next.js 响应式 WebUI 与 PWA 资源
├── docker-compose.yml    本地与自托管编排
├── .env.example          不包含真实密钥的配置模板
└── SHAREWARE.md          专有共享软件使用条款
```

### 当前 MVP 边界

- 一个酒店工作区和一条管理员主流程
- 每个用户对每个服务商连接一个账号
- 当前以“外部日历导入本地时间轴”为主，完整双向回写与冲突合并尚未实现
- Cloudflare Tunnel/DNS API 自动创建流程尚未进入本版
- iOS、Android、DMG 和 EXE 原生封装属于后续工作；当前客户端是响应式 Web/PWA
- 本项目不是 PMS、订房引擎、支付系统或渠道管理器

完整产品规划见 [docs/plan.md](docs/plan.md)。

### 授权说明

版权所有 © 2026 samni728。保留所有权利。

本项目以专有共享软件形式发布，不是开源软件。个人评估和非商业试用必须遵守 [SHAREWARE.md](SHAREWARE.md)；商业使用、对外托管服务、转售和再分发都需要事先取得书面授权或单独的商业许可证。
