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
- synchronize one dedicated hotel calendar across Auto Calendar, Google, and Microsoft;
- access the same UI from desktop browsers, tablets, iPhone, and Android PWA;
- keep application data on infrastructure you control.

The MVP uses its own account/password protection on every network. LAN and ZeroTier are treated as trusted transport paths without an additional gateway login; Cloudflare Tunnel can add Cloudflare Access as a second layer for public access.

### MVP capabilities

- Required first-login setup for the administrator identity, hotel name, timezone, and initial rooms; no fictional hotel or reservation data is preloaded
- Account, display identity, password, hotel, timezone, and room management from the Web UI
- Responsive room timeline with day/week scales, pointer-based event movement, and left/right duration resizing on desktop, tablet, and mobile
- Local event create, update, soft-delete, and overlap protection
- Password login with HttpOnly server sessions and Argon2 password hashing
- Encrypted OAuth token storage using Fernet
- Google Calendar and Microsoft 365 OAuth 2.0 + PKCE connection flow
- Dedicated-calendar creation/selection with two-way, read-only, write-only, and paused modes
- Immediate local-to-provider writes plus manual and scheduled provider-to-provider synchronization
- Per-provider event mapping and content fingerprints to prevent duplicate events and sync loops
- Unassigned-event workflow before an imported event occupies a room
- PostgreSQL persistence and Alembic migrations
- PWA manifest and service worker
- Docker Compose deployment with an Nginx gateway
- Direct source-code mode with an interactive Bash menu and a separate local SQLite development database
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
- The first login opens a required setup flow for the administrator name, display title, hotel, timezone, and rooms.
- Change the temporary password from **Account & Hotel Settings** immediately after setup.

After the first setup, open the interactive Docker management menu whenever you need to start, stop, restart, inspect status, or follow logs:

```bash
./scripts/manage.sh
```

The same script also supports direct commands such as `./scripts/manage.sh start`, `stop`, `restart`, `status`, and `logs api`.

Useful commands:

```bash
docker compose ps
docker compose logs -f api web gateway
docker compose up -d --build
docker compose down
```

`docker compose down` preserves the PostgreSQL volume. `docker compose down -v` permanently removes local database data and should only be used when intentionally resetting a test installation.

### Run directly from source (without Docker)

The source management menu runs FastAPI and Next.js directly. It requires Python 3.12+, Node.js 22+, and npm. By default it uses a separate local SQLite database under `.runtime/source`, so PostgreSQL is not required for development.

```bash
./scripts/manage-source.sh
```

The menu supports installing dependencies, starting, stopping, restarting, checking status, running migrations, and following API/WebUI logs. Direct commands are also available:

```bash
./scripts/manage-source.sh install
./scripts/manage-source.sh start
./scripts/manage-source.sh status
./scripts/manage-source.sh logs api
./scripts/manage-source.sh restart
./scripts/manage-source.sh stop
```

Open [http://localhost:8080](http://localhost:8080). Source mode and Docker mode cannot use port `8080` at the same time; stop one before starting the other. To use a locally installed PostgreSQL instead of SQLite, set `SOURCE_DATABASE_URL` in `.env`.

To allow trusted LAN or ZeroTier devices to open the WebUI, set `SOURCE_WEB_HOST=0.0.0.0` in `.env` and restart source mode. The status command will print the detected LAN URL. FastAPI remains bound to `127.0.0.1`; only the WebUI is exposed. When the OAuth callback still uses `localhost`, complete provider authorization on the server computer, then use the LAN URL normally from phones, tablets, and other computers.

Alembic “migration complete” only means that the database schema is current; it does not copy business data between PostgreSQL and SQLite. To make source mode use a one-time copy of the current Docker data, choose **Import data from Docker PostgreSQL** in the menu or run:

```bash
./scripts/manage-source.sh import-docker
```

The importer stops source services, creates a timestamped SQLite backup, copies users, workspaces, rooms, events, sessions, audit records, and encrypted provider connections, then restarts source mode. Docker PostgreSQL remains the authoritative separate database; later edits are not automatically synchronized between the two databases.

### OAuth configuration

After starting Auto Calendar, open the built-in illustrated guide at [http://localhost:8080/oauth-guide](http://localhost:8080/oauth-guide). The Calendar Connections page also links to this guide. It covers the current Google Cloud and Microsoft Azure/Entra screens, local versus public callback URLs, `.env` binding, and the errors encountered during the first working setup.

Official registration entry points:

- [Google Cloud Console](https://console.cloud.google.com/) → Google Auth Platform → Clients
- [Microsoft Azure Portal](https://portal.azure.com/) → Microsoft Entra ID → App registrations

These are application credentials, not calendar-account passwords. Microsoft values come from **Entra App registrations**, not Microsoft Teams. Copy or update `.env` with credentials created in your own test applications:

```dotenv
PUBLIC_BASE_URL=https://calendar.example.com
SOURCE_PUBLIC_BASE_URL=https://calendar.example.com
SESSION_COOKIE_SECURE=true

GOOGLE_CLIENT_ID='Google OAuth Client ID'
GOOGLE_CLIENT_SECRET='Google OAuth Client secret'

MICROSOFT_CLIENT_ID='Application (client) ID'
MICROSOFT_CLIENT_SECRET='Client secret Value'
MICROSOFT_TENANT=consumers
```

Microsoft tenant selection:

| App registration account type | `MICROSOFT_TENANT` |
| --- | --- |
| Personal Microsoft accounts only (Outlook/Hotmail/MSN) | `consumers` |
| Work/school directories and personal Microsoft accounts | `common` |
| One organization only | its Directory (tenant) ID |

For Microsoft, `MICROSOFT_CLIENT_ID` is **Application (client) ID**, not Object ID or Directory ID. `MICROSOFT_CLIENT_SECRET` is the secret **Value**, not the UUID-shaped Secret ID. The Value is normally shown only when the secret is created.

Register these exact redirect URIs:

- Google: `https://calendar.example.com/api/oauth/google/callback`
- Microsoft: `https://calendar.example.com/api/oauth/microsoft/callback`

For local browser testing, use `PUBLIC_BASE_URL=http://localhost:8080` in Docker mode or `SOURCE_PUBLIC_BASE_URL=http://localhost:8080` in source mode, and register these Web redirect URIs in the same test applications:

- Google: `http://localhost:8080/api/oauth/google/callback`
- Microsoft: `http://localhost:8080/api/oauth/microsoft/callback`

The connection buttons remain disabled when the corresponding Client ID or Client Secret is empty. After changing `.env`, recreate the API container with `./scripts/manage.sh build`, or restart source mode with `./scripts/manage-source.sh restart`.

Google test projects must add the actual authorizing Gmail address under **Google Auth Platform → Audience → Test users**. Otherwise Google returns `Error 403: access_denied`. Testing-mode authorizations that request Calendar access can expire after seven days; use testing mode for the MVP and complete the appropriate production/verification work before opening the integration to other users.

OAuth setup alone is not enough: enable the **Google Calendar API** in the same Google Cloud project as the OAuth client. If the connection page reports `Calendar API has not been used or is disabled`, enable it in the API Library and retry after propagation.

For localhost testing, the browser and Auto Calendar must run on the same computer. For VPS or remote-user access, configure a fixed public HTTPS domain through Cloudflare Tunnel or a reverse proxy, update `PUBLIC_BASE_URL`/`SOURCE_PUBLIC_BASE_URL`, restart the service, and register the newly generated callbacks at both providers. Keep FastAPI port `8000` private.

OAuth consent happens in the user's browser. Client secrets and refresh tokens remain on the server; refresh tokens are encrypted before being stored in the application database. The server then refreshes access tokens and synchronizes the selected dedicated calendar on demand or at the configured interval. Calendar IDs, sync modes, and labels are per-user runtime settings stored in the database—not deployment secrets in `.env`.

For a clean separation from personal events, create the same clearly named dedicated calendar (for example `Auto Calendar · Hotel bookings`) in both providers from the Web UI. A matching name or tag does not itself synchronize anything: Auto Calendar's event-mirror records provide the actual identity mapping. Google receives a private extended property; Outlook also receives the visible category label.

Each full sync uses two phases: first pull changes from every enabled provider, then push the merged workspace state to every writable provider. This lets Google, Outlook, and Auto Calendar converge in the same sync cycle instead of waiting for the next scheduled run.

Requested permissions:

- Google: identity/email, calendar-list read, calendar creation, and calendar-event access
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
- 将一份酒店专用日历在 Auto Calendar、Google 和 Microsoft 之间同步；
- 通过桌面浏览器、Pad、iPhone 和 Android PWA 使用同一个界面；
- 将业务数据保存在自己控制的服务器或 Mac mini 上。

无论通过哪种网络访问，MVP 都保留应用自身的账号密码防护。局域网和 ZeroTier 作为可信传输路径，不额外增加网关登录；Cloudflare Tunnel 公网访问则建议叠加 Cloudflare Access，形成第二层保护。

### MVP 已有能力

- 管理员首次登录必须设置真实姓名、展示身份、酒店名称、时区和初始房间，不再预置虚构酒店、房间或订单
- 在 WebUI 中管理账号身份、密码、酒店、时区和房间
- 响应式房态时间轴，支持日/周单位，以及桌面、Pad、手机上的事件拖动和左右边缘时长调整
- 本地事件新增、修改、软删除和日期冲突保护
- HttpOnly 服务端 Session 与 Argon2 密码哈希
- 使用 Fernet 加密保存 OAuth token
- Google Calendar、Microsoft 365 OAuth 2.0 + PKCE 授权流程
- 创建/选择专用日历，并支持双向、只读、只写和暂停四种模式
- Auto Calendar 本地修改即时回写，以及手动/后台的跨供应商同步
- 使用事件映射与内容指纹防止重复事件和同步回环
- 外部事件待分配机制，避免导入后误占房间
- PostgreSQL 持久化和 Alembic 数据库迁移
- PWA manifest 与 Service Worker
- Docker Compose 和 Nginx 统一入口
- 带交互式 Bash 菜单的纯源码运行模式，以及独立的本地 SQLite 开发数据库
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
- 第一次登录会强制填写管理员姓名、展示身份、酒店、时区和房间。
- 初始化完成后，请立即在“账号与酒店设置”中修改临时密码。

首次初始化完成后，可以随时打开 Docker 中文管理菜单，用于启动、停止、重启、查看状态和实时日志：

```bash
./scripts/manage.sh
```

同一个脚本也支持直接命令，例如 `./scripts/manage.sh start`、`stop`、`restart`、`status` 和 `logs api`。

常用命令：

```bash
docker compose ps
docker compose logs -f api web gateway
docker compose up -d --build
docker compose down
```

`docker compose down` 不会删除 PostgreSQL 数据卷。`docker compose down -v` 会永久删除本地数据库数据，只应在明确重置测试环境时使用。

### 不使用 Docker，直接运行源码

源码管理菜单会直接运行 FastAPI 与 Next.js，需要 Python 3.12+、Node.js 22+ 和 npm。源码开发模式默认使用 `.runtime/source` 下的独立 SQLite 数据库，因此不要求本机另外安装 PostgreSQL。

```bash
./scripts/manage-source.sh
```

菜单支持安装依赖、启动、停止、重启、查看状态、数据库迁移，以及查看 API/WebUI 实时日志。也可以直接使用命令：

```bash
./scripts/manage-source.sh install
./scripts/manage-source.sh start
./scripts/manage-source.sh status
./scripts/manage-source.sh logs api
./scripts/manage-source.sh restart
./scripts/manage-source.sh stop
```

启动后访问 [http://localhost:8080](http://localhost:8080)。源码模式与 Docker 模式不能同时占用 `8080` 端口，启动其中一种之前需要先停止另一种。如需使用本机 PostgreSQL，可在 `.env` 中设置 `SOURCE_DATABASE_URL`。

若要让可信局域网或 ZeroTier 设备访问 WebUI，在 `.env` 设置 `SOURCE_WEB_HOST=0.0.0.0` 后重启源码服务，状态页面会显示自动检测到的局域网地址。FastAPI 仍只监听 `127.0.0.1`，对外仅开放 WebUI。OAuth callback 仍使用 localhost 时，请在运行服务的电脑上完成 Google/Microsoft 授权；授权后手机、Pad 和其他电脑可以正常通过局域网地址使用。

菜单中的“Alembic 迁移完成”只表示数据库表结构已升级，并不会自动把 PostgreSQL 业务数据复制到 SQLite。若要让源码模式一次性继承当前 Docker 数据，请在菜单选择“从 Docker PostgreSQL 导入数据”，或者运行：

```bash
./scripts/manage-source.sh import-docker
```

导入器会先停止源码服务、为当前 SQLite 创建带时间戳的备份，然后复制用户、酒店、房间、事件、Session、审计记录和加密的日历连接，最后重新启动源码服务。Docker PostgreSQL 与 SQLite 仍是两套独立数据库，之后发生的新修改不会自动在两边同步。

### OAuth 配置

启动 Auto Calendar 后，可直接打开内置图文教程：[http://localhost:8080/oauth-guide](http://localhost:8080/oauth-guide)。日历连接页面也提供该入口。教程包含目前实际的 Google Cloud、Microsoft Azure/Entra 页面截图、localhost/公网回调、`.env` 参数绑定，以及第一次配置时踩过的错误。

官方注册网址：

- [Google Cloud Console](https://console.cloud.google.com/) → Google Auth Platform → Clients
- [Microsoft Azure Portal](https://portal.azure.com/) → Microsoft Entra ID → App registrations

这里创建的是 Auto Calendar 的“应用凭据”，不是日历账号密码。Microsoft 参数来自 **Entra 应用注册**，不是 Microsoft Teams。在 `.env` 中填写自己测试应用生成的凭据：

```dotenv
PUBLIC_BASE_URL=https://calendar.example.com
SOURCE_PUBLIC_BASE_URL=https://calendar.example.com
SESSION_COOKIE_SECURE=true

GOOGLE_CLIENT_ID='Google OAuth Client ID'
GOOGLE_CLIENT_SECRET='Google OAuth Client secret'

MICROSOFT_CLIENT_ID='Application (client) ID'
MICROSOFT_CLIENT_SECRET='Client secret 的 Value'
MICROSOFT_TENANT=consumers
```

Microsoft Tenant 选择规则：

| App registration 支持的账号类型 | `MICROSOFT_TENANT` |
| --- | --- |
| 仅个人 Microsoft 账号（Outlook/Hotmail/MSN） | `consumers` |
| 企业/学校目录 + 个人 Microsoft 账号 | `common` |
| 仅一个企业/学校组织 | 该组织的 Directory (tenant) ID |

`MICROSOFT_CLIENT_ID` 必须填写 **Application (client) ID**，不能填写 Object ID 或 Directory ID；`MICROSOFT_CLIENT_SECRET` 必须填写 Client secret 的 **Value**，不能填写 UUID 形式的 Secret ID。Value 通常只在创建密钥时完整显示一次。

在服务商后台精确登记以下 Redirect URI：

- Google：`https://calendar.example.com/api/oauth/google/callback`
- Microsoft：`https://calendar.example.com/api/oauth/microsoft/callback`

如需在本地浏览器测试，Docker 模式使用 `PUBLIC_BASE_URL=http://localhost:8080`，源码模式使用 `SOURCE_PUBLIC_BASE_URL=http://localhost:8080`，并在同一套测试应用中增加以下 Web Redirect URI：

- Google：`http://localhost:8080/api/oauth/google/callback`
- Microsoft：`http://localhost:8080/api/oauth/microsoft/callback`

只要对应的 Client ID 或 Client Secret 为空，连接按钮就会保持禁用。修改 `.env` 后，Docker 模式运行 `./scripts/manage.sh build` 重建 API 容器；源码模式运行 `./scripts/manage-source.sh restart`。

Google 测试应用必须在 **Google Auth Platform → Audience → Test users** 中加入实际用于授权的 Gmail，否则会出现 `Error 403: access_denied`。申请 Calendar 权限的 Testing 授权可能在 7 天后失效；个人 MVP 先用测试模式跑通，正式开放其他用户前再完成相应的 Production/验证工作。

只创建 OAuth Client 还不够，必须在同一个 Google Cloud Project 中启用 **Google Calendar API**。如果连接页提示 `Calendar API has not been used or is disabled`，请到 API Library 启用后等待几分钟再重试。

localhost 只适合浏览器与 Auto Calendar 位于同一台电脑的测试。部署到 VPS 或供异地用户访问时，需要通过 Cloudflare Tunnel 或反向代理准备固定公网 HTTPS 域名，更新 `PUBLIC_BASE_URL`/`SOURCE_PUBLIC_BASE_URL`，重启服务，然后把新 callback 逐字登记到两个供应商后台。FastAPI 的 `8000` 端口应继续留在内网。

OAuth 登录和授权在用户浏览器中完成。Client Secret 与 refresh token 只保存在服务端，refresh token 加密后写入应用数据库。服务器随后可以刷新 access token，并按照配置周期或手动触发同步所选专用日历。日历 ID、同步模式和分类名称属于每个用户的运行时设置，保存在数据库中，不应写进 `.env`。

为避免干扰私人日程，建议在 WebUI 中分别为 Google 和 Microsoft 创建同名专用日历，例如 `Auto Calendar · 酒店订房`。同名日历或 tag 本身不会产生同步；真正的跨平台对应关系由 Auto Calendar 的事件映射表维护。Google 使用私有扩展属性标记，Outlook 事件还会显示所设置的分类名称。

“同步全部日历”采用两阶段处理：先拉取所有已启用来源的变更，再把合并后的工作区事件推送到所有允许写入的目标，因此 Google、Outlook 与 Auto Calendar 可在同一轮同步中收敛，无须再等下一次定时任务。

申请的主要权限：

- Google：身份/邮箱、日历列表读取、创建日历和日历事件访问
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
- 当前双向同步采用 MVP 冲突规则：本地待同步修改优先，否则按供应商最新变更更新；复杂冲突中心属于后续版本
- Cloudflare Tunnel/DNS API 自动创建流程尚未进入本版
- iOS、Android、DMG 和 EXE 原生封装属于后续工作；当前客户端是响应式 Web/PWA
- 本项目不是 PMS、订房引擎、支付系统或渠道管理器

完整产品规划见 [docs/plan.md](docs/plan.md)。

### 授权说明

版权所有 © 2026 samni728。保留所有权利。

本项目以专有共享软件形式发布，不是开源软件。个人评估和非商业试用必须遵守 [SHAREWARE.md](SHAREWARE.md)；商业使用、对外托管服务、转售和再分发都需要事先取得书面授权或单独的商业许可证。
