# 结论：这不是“可换皮日历”，而是一套业务时间视图引擎

你现在描述的产品，应该从“多端同步日历”升级为：

> **统一时间数据内核 + 行业业务模板 + 个人视图预设 + 外部系统连接器**

同一份底层数据，可以根据用户身份切换成：

* 酒店房态视图；
* 工厂设备与运维视图；
* 多企业管理视图；
* 普通个人日历；
* 项目里程碑视图；
* 生产排期视图；
* 以后甚至可以扩展为门店预约、医生排班、车辆调度。

关键不是给日历换颜色，而是让不同业务对象在“时间轴”上以不同方式呈现。

---

# 零、先冻结第一阶段的产品边界

这套产品长期可以服务酒店、工厂、企业管理等多个行业，但MVP不能同时服务所有行业。

## 第一阶段服务谁

第一阶段的主用户定义为：

> **需要自托管、希望在手机和电脑上统一查看房态与日历的小型酒店经营者或店长。**

部署管理员、前台、保洁和维修人员都是相关角色，但第一版先保证经营者或店长能完成核心工作，不在MVP中展开复杂组织架构和权限矩阵。

## 解决的首要痛点

第一版只解决一个核心问题：

> **酒店的房间、预订、维修和外部日历数据分散，管理者无法通过一个可信的时间视图掌握当前与未来房态。**

第一版不同时承担完整PMS、ERP、财务、CRM或通用低代码平台的职责。

## MVP第一条闭环

```text
管理员用Docker部署
  → 选择Cloudflare、局域网、ZeroTier中的一个或多个入口
  → 配置每个入口的网络边界并创建应用管理员账号
  → 店长使用应用账号密码登录并连接外部日历或导入示例数据
  → 系统把事件映射到房间资源时间轴
  → 店长创建或调整预订/维修事件
  → 数据持久化并同步回来源系统
  → 首页显示今日房态与未来7/14天占用情况
```

这个闭环只保留：

* 一个主用户：酒店经营者或店长；
* 一个主场景：查看并调整房态；
* 一个主数据流：外部日历/人工录入 → 统一时间模型 → 房态视图 → 受控写回；
* 一个主交付结果：手机与电脑都能访问的可信房态时间轴。

## 部署和数据原则

第一阶段采用**本地优先、云入口混合部署**：

* Web、API、Worker、PostgreSQL和Redis运行在用户自己的Docker主机；
* Cloudflare可选负责DNS、TLS、Tunnel与公网入口身份验证；
* ZeroTier可选负责跨公网的私有设备网络，局域网入口只服务明确绑定的本地网卡；
* PWA提供桌面和移动端统一体验，原生App进入后续路线；
* Google、Microsoft等外部系统仍是各自数据的来源之一；
* 本地数据库负责统一映射、业务状态、审计记录和同步游标；
* 必须提供数据库备份、恢复演练、Token轮换和数据导出能力。

## 1到3天内的最小可验证成果

先完成一个可丢弃的技术验证，而不是直接建设完整平台：

1. Docker Compose启动Web、API、PostgreSQL和`cloudflared`；
2. 自动或半自动创建一个Tunnel、一个测试域名和一条邮箱Allow规则；
3. 指定邮箱通过Cloudflare Access登录；
4. PWA在手机、Pad和桌面断点下显示10个模拟房间和一周模拟订单；
5. 新建一条维修事件后刷新页面仍然存在；
6. 未授权邮箱、绕过Access的请求和未匹配域名都被拒绝。

该验证通过后，再进入外部日历双向同步和正式酒店模板开发。

---

# 一、产品的核心架构应重新分为五层

```text
Google Calendar / Microsoft 365 / ERP / PMS / 自有系统
                            │
                    连接器与同步层
                            │
                    统一时间数据模型
                            │
                     行业模板解释器
                            │
                  视图渲染器 + 个人预设
                            │
        Mac / Windows / iPad / Android Pad / iPhone / Android PWA
```

## 1. 统一时间数据内核

底层不再只有传统的`CalendarEvent`，而是至少包含：

```text
Workspace          工作空间
Organization       企业、酒店、工厂、门店
ResourceType       房间、设备、产线、项目、企业、人员
Resource           302房、灌装线A、某个子公司
TimelineEvent      时间事件
EventResourceLink  事件与资源关系
ProviderConnection Google或Microsoft连接
ProviderEventLink  外部日历事件映射
TemplateDefinition 行业模板
ViewPreset         用户个人视图配置
FieldMapping       外部系统字段映射
```

账号与权限不能依赖网络入口临时推断，还需要独立的安全模型：

```text
User                应用用户
UserCredential      密码哈希、状态和安全版本
UserSession         登录会话、过期和撤销状态
WorkspaceMembership 用户与工作空间关系
Role / Permission   角色和权限
IdentityAccount     可选的Cloudflare/Google/Microsoft身份映射
AuditLog            用户、入口、操作对象和结果审计
```

其中最重要的是`Resource`。

传统日历只知道“人在什么时间做什么”，而你的产品要知道：

* 哪个房间在什么日期被占用；
* 哪台设备在什么时间维修；
* 哪条产线在什么班次生产；
* 哪个企业在什么日期有付款、审计、合同、会议；
* 哪个项目在什么时间出现里程碑。

因此它实际上是：

> **时间 × 资源 × 状态 × 业务数据**

## 2. 多端客户端与响应式架构

客户端从第一天就按“同一业务内核、多种终端形态”设计：

```text
React/Vite共享前端核心
    ├─ Desktop Web：Mac / Windows浏览器
    ├─ Tablet Web/PWA：iPad / Android Pad
    ├─ Mobile PWA：iPhone / Android
    ├─ Future Mobile Shell：iOS / Android App
    └─ Future Desktop Shell：DMG / EXE
```

第一版交付响应式WebUI和PWA；后续App、DMG和EXE只封装客户端，不把FastAPI、PostgreSQL或同步Worker打包进终端。所有终端都通过同一套版本化API访问Docker服务器。

### 各终端的信息布局

不是简单按比例缩小桌面页面，而是共享业务能力、按屏幕重新编排：

| 终端 | 主要场景 | 推荐布局 |
| --- | --- | --- |
| 手机 `<768px` | 快速查看今日房态、入住离店、处理单个事件 | 底部导航、单列卡片、横向滑动紧凑时间轴、全屏编辑页 |
| Pad `768–1199px` | 前台与店长日常操作 | 房间时间轴为主、可折叠侧栏、详情抽屉、横竖屏适配 |
| Desktop `≥1200px` | 高密度排房、批量操作、同步管理 | 侧栏 + 14/30天时间轴 + 固定详情面板、键盘与鼠标快捷操作 |

酒店主视图在三端保持相同的数据和权限，但呈现不同：

```text
手机：今日看板 → 房间/事件列表 → 单事件操作
Pad：房间时间轴 ↔ 详情抽屉
桌面：筛选侧栏 + 高密度时间轴 + 常驻详情面板
```

时间轴可以自身横向滚动，但页面不能出现意外的全局横向溢出。

### 前端实现边界

前端必须遵守：

* 业务规则、冲突检测、权限和同步状态以服务端为准；
* 不在组件中直接调用Google或Microsoft API；
* 不把Refresh Token、Cloudflare Token或其他长期密钥放入浏览器；
* 路由、状态和表单模型在各端共享，布局组件可以按断点替换；
* 不假设设备一定有鼠标、Hover、键盘、摄像头或文件系统；
* 触摸目标、焦点顺序、键盘操作、颜色对比和屏幕阅读器语义必须纳入组件规范；
* 支持刘海屏和底部Home Indicator的Safe Area；
* 关键操作不能只依赖右键、Hover或拖拽，必须提供按钮或表单替代路径。

浏览器和未来原生外壳能力通过统一适配层访问：

```text
ClientPlatformAdapter
    openExternalAuth()
    handleAuthReturn()
    installPrompt()
    notifications()
    secureClientStorage()
    fileExport()
    appLifecycle()
    networkStatus()
```

Web/PWA先实现浏览器版本；未来封装iOS、Android、DMG或EXE时替换Adapter，不修改酒店Domain、API契约和页面业务状态。

### PWA第一版边界

第一版PWA支持：

* Web App Manifest、图标、主题色和可安装入口；
* 响应式页面和Standalone显示模式；
* 缓存静态应用壳，提高弱网下的启动速度；
* 网络状态提示、请求失败重试和同步状态反馈；
* Google/Microsoft OAuth通过系统浏览器或顶层跳转完成，并能返回原页面；
* iOS Safari、iOS主屏PWA、Android Chrome/PWA以及桌面主流浏览器。

MVP不做离线写入。Service Worker不得缓存登录响应、私有API响应或带用户数据的HTML；离线只显示静态壳和明确的断网状态。离线只读快照、离线Outbox和推送通知进入Next。

### 为App、DMG和EXE预留的接口

未来客户端封装需要预留：

* 自定义URL Scheme或Universal/App Link接收OAuth回跳；
* 客户端版本与服务端API版本兼容检查；
* 系统安全存储保存短期客户端凭据，不保存Provider Refresh Token；
* 系统通知、Dock/托盘、Badge和后台生命周期适配；
* 文件导出、相机、分享等能力通过Adapter调用；
* 自动更新、签名、公证和应用商店规则由各平台构建流程负责。

是否采用WebView封装、跨端框架或更原生的客户端实现，在PWA闭环跑通后再决定。当前只保证API优先、状态解耦和平台能力隔离，不提前建设多套客户端。

### 多端验收基线

至少验证以下组合：

| 平台 | 视口/形态 | 必测流程 |
| --- | --- | --- |
| iPhone Safari/PWA | `390×844`附近、竖屏 | 登录、今日看板、查看/编辑事件、OAuth回跳 |
| Android Chrome/PWA | 常见手机视口 | 安装、登录、时间轴滑动、表单和断网提示 |
| iPad Safari/PWA | `768×1024`、横竖屏 | 房间时间轴、详情抽屉、切换方向后状态保留 |
| Android Pad | `800–1280px`范围 | 触控操作、滚动、筛选和编辑 |
| Desktop Web | `1440px`及以上 | 高密度时间轴、键盘操作、同步中心和管理页面 |

每个平台都必须通过应用账号登录、权限拦截、OAuth连接、房态查看和事件编辑，不能只验证首页能打开。

---

# 二、模板应当包含业务语义，而不只是视觉样式

一个行业模板至少应定义七类内容：

| 模板内容 | 作用                             |
| ---- | ------------------------------ |
| 资源模型 | 房间、设备、产线、企业、项目、人员              |
| 事件类型 | 入住、离店、维修、停机、审计、回款              |
| 状态体系 | 已预订、已入住、待清洁、维修中、已完成            |
| 默认视图 | 月历、资源时间轴、矩阵、看板、列表              |
| 快速表单 | 新增事件时显示哪些字段                    |
| 指标卡片 | 入住率、停机时长、逾期事项、设备利用率            |
| 映射规则 | 如何把Google、Outlook或业务系统数据转换为该模板 |

## 酒店模板

| 项目   | 酒店视角                        |
| ---- | --------------------------- |
| 资源   | 酒店、楼层、房型、房间                 |
| 时间单位 | 天、晚                         |
| 核心状态 | 预订、入住、离店、待清洁、维修、锁房          |
| 默认视图 | 房间 × 日期占用矩阵                 |
| 关键指标 | 入住率、空房数、今日入住、今日离店           |
| 快速操作 | 延住、换房、锁房、维修、退房              |
| 数据来源 | Google、Outlook、PMS、你的入住管理系统 |

视觉上可以是：

```text
房间       8/17       8/18       8/19       8/20
302       王女士入住 ────────────────── 离店
303       空房       李先生入住 ─────── 离店
305       维修       维修       待清洁    可入住
401       团队预订 ──────────────────────
```

## 工厂模板

| 项目   | 工厂视角                 |
| ---- | -------------------- |
| 资源   | 工厂、车间、产线、设备、班组       |
| 时间单位 | 小时、班次、天              |
| 核心状态 | 运行、换线、维修、保养、质检、停机    |
| 默认视图 | 设备时间轴、班次看板、维护日历      |
| 关键指标 | 停机时长、设备利用率、维护逾期、异常次数 |
| 快速操作 | 报修、安排保养、停机、恢复、派工     |
| 数据来源 | ERP、MES、设备接口、人工录入    |

视觉上不再是普通日历，而是：

```text
设备/产线     08:00      12:00      16:00      20:00
灌装线A      生产订单01 ───── 换线 ── 生产订单02
包装线B      运行 ─────────── 故障维修 ─── 恢复
注塑机03     保养 ──────── 待质检 ─────── 生产
```

## 企业管理模板

| 项目   | 企业管理视角                         |
| ---- | ------------------------------ |
| 资源   | 企业、子公司、部门、项目、负责人               |
| 时间单位 | 天、周、月、季度                       |
| 核心状态 | 会议、合同、付款、审计、申报、里程碑             |
| 默认视图 | 多企业时间轴、截止日期看板、风险热力图            |
| 关键指标 | 本周待办、逾期事项、关键会议、待回款             |
| 快速操作 | 分派、延期、确认、催办、关联文档               |
| 数据来源 | Outlook、Google、ERP、CRM、飞书、自有系统 |

这时用户看到的不是“我的日历”，而是：

```text
企业A    合同签署     回款节点       月度经营会
企业B    审计准备     税务申报       董事会
企业C    新品立项     供应商确认     量产节点
```

---

# 三、工作空间模板与个人视图必须分开

这是避免后期混乱的关键设计。

## 工作空间模板

由企业或管理员决定，定义共同业务规则：

* 有哪些资源；
* 有哪些状态；
* 字段是什么意思；
* 哪些数据可以修改；
* 哪些数据来自业务系统；
* 哪些指标需要计算。

例如酒店工作空间统一规定：

```text
资源 = 房间
入住日期和离店日期必须填写
维修状态不可被普通员工覆盖
入住率按照可售房间计算
```

## 个人视图预设

每个用户可以按照自己的习惯配置：

* 默认打开今天、7天、14天还是30天；
* 按酒店、楼层、房型还是入住状态分组；
* 显示或隐藏客人姓名；
* 是否显示空房；
* 颜色、密度、字号；
* 只查看自己负责的企业；
* 默认筛选哪些日历；
* 移动端首页显示哪些指标。

例如同一家酒店：

```text
前台：今日入住、离店、待清洁
店长：入住率、空房、维修房、未来14天
保洁：待清洁、已清洁、需要复查
维修：维修中、待维修、停用房
```

所以系统里应该有两个不同对象：

```text
WorkspaceTemplate
UserViewPreset
```

不能让用户修改个人呈现方式时破坏整个企业的业务模板。

---

# 四、模板建议采用“80%声明式 + 20%插件式”

第一版不要做复杂的可视化拖拽模板编辑器，那会显著拖慢开发。

第一阶段可以把模板定义成JSON或YAML：

```yaml
id: hotel-operations
version: 1

resource:
  type: room
  group_by:
    - property
    - floor
    - room_type

event_types:
  - reserved
  - checked_in
  - checking_out
  - cleaning
  - maintenance
  - blocked

views:
  default: occupancy_timeline
  available:
    - today_board
    - occupancy_timeline
    - month_calendar
    - event_list

quick_create:
  fields:
    - room
    - status
    - start_date
    - end_date
    - booking_source
    - guest_name

metrics:
  - occupancy_rate
  - vacant_rooms
  - arrivals_today
  - departures_today

permissions:
  maintenance:
    editable_by:
      - manager
      - maintenance_staff
```

前端不执行模板中的任意JavaScript，只允许模板引用系统注册过的组件：

```text
month_calendar
resource_timeline
occupancy_matrix
today_board
deadline_board
operations_heatmap
```

这样可以做到：

* 安全；
* 可升级；
* 容易让Codex生成；
* 模板可以版本化；
* 模板可以导入导出；
* 后期可以建立模板市场；
* 不需要为每个行业Fork一套前端。

复杂需求再通过插件扩展：

```text
HotelOccupancyWidget
FactoryDowntimeWidget
EnterpriseRiskWidget
```

---

# 五、与业务系统对接时，不应把Calendar当作唯一数据源

酒店PMS、ERP、MES或你自己的系统接入后，需要定义“主数据归属”。

每个连接器应配置三种模式之一：

## 1. 只读投影视图

业务系统是主数据源。

```text
PMS预订
  → 同步到业务日历
  → 用户可以查看、筛选、统计
  → 不允许直接修改关键预订信息
```

适合酒店正式订单、ERP生产订单。

## 2. 受控双向同步

用户可以在日历中操作，但实际上是向业务系统发送命令：

```text
用户把302房延长一天
  → 生成“延住请求”
  → 调用PMS接口
  → PMS确认成功
  → 更新日历
```

## 3. 日历主导

适合普通会议、内部维护计划、提醒：

```text
日历中新建维修计划
  → 保存到本系统
  → 同步到Outlook或Google
```

每个事件应保留：

```text
source_system
source_record_id
source_of_truth
writeback_policy
sync_status
external_version
```

这样未来接入你的酒店系统、ERP或其他接口时，不会出现“Google改了、业务系统也改了，最后谁覆盖谁”的问题。

---

# 六、Cloudflare Tunnel + Access方向是正确的

Cloudflare Tunnel通过`cloudflared`从服务器主动向Cloudflare建立连接，源站不需要公网IP，也可以在阻止所有入站连接的情况下只允许`cloudflared`出站。`cloudflared`本身也有官方Docker运行方式。([Cloudflare Docs][1])

因此Docker部署可以做到：

```text
服务器不开放应用端口
不需要公网IP
不需要路由器端口转发
应用容器只在Docker内部网络通信
只有cloudflared连接Cloudflare
```

但“可以少考虑防火墙”不等于“可以不考虑安全”。

最低限度仍要保留四层：

1. Cloudflare Access负责外部身份验证；
2. 应用后端验证Cloudflare传入的Access JWT；
3. 应用自身负责工作空间、角色、数据权限；
4. Google和Microsoft的Refresh Token在数据库中加密保存。

Cloudflare会在已认证请求中添加`Cf-Access-Jwt-Assertion`，官方也明确要求源站验证Access令牌，防止因路由或网络错误导致请求绕过Access。([Cloudflare Docs][2])

## Cloudflare自动配置的产品边界

这里需要把两件事区分开：

```text
Cloudflare Tunnel Public Hostname
    负责：公网域名 → Docker内部服务与端口

Cloudflare Access / Zero Trust
    负责：哪些身份可以访问该公网域名
```

因此，“域名指向本地服务”由Tunnel路由和DNS记录完成；“指定Gmail账号或邮箱才能访问”由Access应用、身份提供商和Allow策略完成。两部分都成功后，才算真正完成安全开放。

推荐使用**远程管理、Token模式的Tunnel**。Cloudflare API可以创建Tunnel、写入Ingress规则、创建指向`<tunnel-id>.cfargotunnel.com`的代理CNAME，并获取供`cloudflared`运行的Tunnel Token。域名必须属于当前Cloudflare账号中的有效Zone。([Cloudflare Docs][12])

## 配置参数契约

部署引导器至少需要以下参数：

| 参数 | 必填 | 作用 | 保存策略 |
| --- | --- | --- | --- |
| `CF_ACCOUNT_ID` | 是 | Cloudflare账号范围 | 普通配置 |
| `CF_ZONE_ID` | 建议 | 域名所在Zone；也可根据根域名查询 | 普通配置 |
| `CF_API_TOKEN` | 初始化时 | 创建Tunnel、DNS、Access应用与策略 | 只在引导阶段使用，不进入前端、不写日志 |
| `CF_BASE_DOMAIN` | 是 | 例如`example.com` | 普通配置 |
| `CF_APP_HOSTNAME` | 是 | 例如`calendar.example.com` | 普通配置 |
| `CF_TUNNEL_NAME` | 是 | 例如`auto-calendar-prod` | 普通配置 |
| `CF_TUNNEL_TOKEN` | 自动生成 | `cloudflared`连接指定Tunnel | Docker Secret或权限为`0600`的独立环境文件 |
| `CF_ACCESS_ALLOWED_EMAILS` | 是 | 精确邮箱白名单，逗号分隔 | 管理配置，不是密钥 |
| `CF_ACCESS_ALLOWED_DOMAINS` | 否 | 企业邮箱域名白名单 | 默认留空 |
| `CF_ACCESS_LOGIN_MODE` | 是 | `otp`、`google`或企业IdP | 普通配置 |

这里的“API接口”应落实为**最小权限API Token**，不要使用Global API Key。自动创建Tunnel、DNS和Access时，Token通常至少需要当前账号的Tunnel写权限、Access Apps and Policies写权限，以及目标Zone的DNS写权限；若还要自动创建OTP或其他身份提供商，则需要相应的Identity Provider写权限。实际权限名称以Cloudflare控制台当前显示为准。([Cloudflare Docs][16])

如果只输入根域名而不输入`CF_ZONE_ID`，引导器可以查询Zone ID，但需要额外的Zone读取权限。生产环境更推荐显式配置Zone ID，以减少Token权限和自动推断。

## 自动生成和端口匹配流程

第一版不要让常驻业务API直接管理Cloudflare。应提供一个只在本机运行的部署引导器，例如：

```text
python -m deploy.cloudflare bootstrap
```

或者提供仅监听`127.0.0.1`的初始化页面。它负责一次性配置，成功后退出。

建议的自动化流程如下：

```text
读取配置
  → 验证API Token、Account ID、Zone ID和域名归属
  → 按名称查询Tunnel，存在则复用，不存在则创建
  → 在公网路由生效前创建默认拒绝的Access应用
  → 创建指定邮箱/企业域名的Allow策略
  → 生成Ingress：hostname → Docker服务名:容器端口
  → 创建或校正代理CNAME → <tunnel-id>.cfargotunnel.com
  → 获取Tunnel Token并写入Docker Secret
  → 启动或重建cloudflared容器
  → 检查Tunnel健康、DNS解析、Access拦截和源站响应
  → 保存资源ID、配置摘要和审计结果
```

必须采用**幂等式Reconcile**，而不是每次点击都新建资源：

* 同名Tunnel存在时更新配置；
* 同主机名DNS记录存在时校验目标并修正；
* 同域名Access应用存在时更新Allow列表；
* 对不属于本项目的同名资源停止操作并提示冲突；
* 每一步记录Cloudflare资源ID，失败后可以从上一步恢复；
* 删除Tunnel、DNS或Access应用必须是独立的显式危险操作，不能随普通卸载自动执行。

Cloudflare建议先创建Access应用，再发布Tunnel路由，否则域名可能在Access策略建立前短暂对所有公网用户开放。Access应用本身默认拒绝，只有命中Allow策略的用户可以进入。([Cloudflare Docs][13])

### Docker服务与端口映射

`cloudflared`运行在Compose网络中时，Origin地址必须使用**Docker服务名和容器端口**，不能使用宿主机的`localhost`：

```text
calendar.example.com
    → http://calendar-web:3000
    → Cloudflare Access保护

hooks.calendar.example.com
    → http://webhook-receiver:8081
    → 应用自行验证Webhook

oauth.calendar.example.com
    → http://calendar-api:8000
    → 应用自行验证state、PKCE和授权码

未匹配的主机名
    → http_status:404
```

自动化模块要验证：服务名存在、端口是容器监听端口、Ingress最后有`http_status:404`兜底、应用没有通过`ports`意外发布到公网。

更稳妥的MVP是只让`cloudflared`访问一个内部网关：

```text
calendar.example.com → http://calendar-gateway:8080
```

再由网关按`/api`、`/oauth`、`/webhooks`和静态资源分发。这样浏览器端同源，PWA、Cookie和CORS更简单；Webhook与OAuth回调仍需在Access中使用精确路径规则，并由应用自行验证。

MVP只允许Cloudflare引导器发布本项目预先登记的`calendar-gateway:8080`，不提供任意IP、宿主机端口或Docker服务的公网映射输入。把它扩展成“通用内网服务发布平台”属于Later范围，会引入横向访问、SSRF、误暴露管理后台和权限审计等额外风险，不能混入当前日历产品闭环。

## Zero Trust邮箱授权策略

权限控制提供两种MVP模式：

### 模式A：指定邮箱 + One-time PIN，推荐作为第一版

管理员填写：

```text
owner@gmail.com
manager@example.com
frontdesk@example.com
```

部署引导器创建Access Allow策略，`Include`使用精确的`Emails`列表。用户输入邮箱后通过一次性验证码登录，不需要先配置Google OAuth客户端。Cloudflare支持向Access策略允许的邮箱发送一次性验证码。([Cloudflare Docs][15])

### 模式B：Google或企业身份提供商

如果希望出现“使用Google继续”，需要在Cloudflare Zero Trust中配置Google或Google Workspace身份提供商，并准备对应的Google OAuth Client ID和Client Secret。Access策略仍然应使用精确邮箱或企业域名限制，而不是只要Google登录成功就放行。

策略规则：

* 个人Gmail账号使用精确邮箱列表；
* **绝不能配置`@gmail.com`域名Allow**，否则任何Gmail用户都可能进入；
* 企业自有域名可以使用`Emails ending in @company.com`，但要确认该域名身份由可信IdP验证；
* 不创建`Include Everyone`；
* OTP登录必须同时绑定精确邮箱或受控企业域名，不能把“One-time PIN”本身作为放行条件；
* 外部合作方优先使用独立Access组，方便撤权和审计；
* Access只决定能否进入应用，进入后的酒店、工作空间、角色和字段权限仍由应用RBAC决定。

Access的多条`Include`条件按OR组合，`Require`条件按AND组合；自动生成策略前应先在本地把规则编译成可读摘要，避免错误组合造成过度授权。([Cloudflare Docs][14])

## 密钥、审计和恢复

Cloudflare自动配置必须遵守以下安全边界：

* `CF_API_TOKEN`只进入部署引导器，不进入PWA、浏览器Local Storage、普通业务日志或数据库明文字段；
* `CF_TUNNEL_TOKEN`虽然权限小于管理Token，但持有者可以启动该Tunnel的副本，仍必须按密钥处理并支持轮换。([Cloudflare Docs][17])
* 不给业务容器挂载Docker Socket；部署引导器通过明确的Compose命令完成重建；
* 自动配置结果只保存资源ID、状态、时间、操作者和脱敏错误，不保存完整Token；
* 后端继续验证Access JWT；Service Worker不得缓存Access登录响应、私有API响应或带身份信息的HTML；
* PostgreSQL和Redis不加入`cloudflared`所在的edge网络，只允许内部API/Worker访问；
* 提供“本地恢复入口”：公网配置失败时，管理员可从服务器本机运行诊断、轮换Token或关闭Tunnel；
* 生产环境至少运行两个`cloudflared`副本或准备快速恢复方式，并监控Tunnel从Healthy变为Down。

建议为自动配置维护明确状态机：

```text
unconfigured
  → validating
  → provisioning_tunnel
  → provisioning_access
  → provisioning_dns
  → connector_starting
  → healthy
  → degraded / error
```

只有进入`healthy`且未授权邮箱测试被拒绝后，界面才显示“公网访问已安全开放”。

## 推荐域名划分

```text
calendar.example.com
    PWA和应用API
    Cloudflare Access保护

hooks.calendar.example.com
    Google和Microsoft Webhook
    不使用交互式Access登录
    由应用验证Webhook来源

oauth.calendar.example.com
    Google和Microsoft OAuth Callback
    验证state、PKCE和授权码
```

也可以使用同一个域名，通过路径区分：

```text
calendar.example.com/*
    Access保护

calendar.example.com/oauth/*/callback
    精确路径Bypass

calendar.example.com/webhooks/*
    精确路径Bypass
```

Cloudflare Access官方支持针对OAuth回调、Webhook接收器等特定路径设置Bypass，但Bypass意味着该路径不再享受Access安全检查，因此必须由应用自行校验。([Cloudflare Docs][3])

## Cloudflare、局域网和ZeroTier三种访问入口

部署时不做强制三选一，而是提供三个可以独立开关的入口：

```text
Cloudflare入口
    公网HTTPS → Cloudflare Access → cloudflared → public gateway

局域网入口
    可信LAN设备 → 指定LAN IP与端口 → lan gateway

ZeroTier入口
    已授权ZeroTier设备 → ZeroTier Managed IP与端口 → zerotier gateway
```

配置可以表达为：

```text
ACCESS_CLOUDFLARE_ENABLED=true|false
ACCESS_LAN_ENABLED=true|false
ACCESS_ZEROTIER_ENABLED=true|false

LAN_BIND_IP=192.168.1.10
LAN_TRUSTED_CIDRS=192.168.1.0/24

ZEROTIER_NETWORK_ID=<16位Network ID>
ZEROTIER_BIND_IP=<服务端Managed IP>
ZEROTIER_TRUSTED_CIDRS=<ZeroTier Managed IP段>

APP_AUTH_REQUIRED=true
APP_PUBLIC_SIGNUP_ENABLED=false
```

三个入口可以同时开启，例如：

* 外出时通过Cloudflare域名访问；
* 办公室内通过局域网直接访问；
* 管理员和固定设备通过ZeroTier私网访问。

### 三种入口的认证与权限模型

网络入口只决定请求是否能够到达应用，**所有入口都必须经过应用自身的账号密码、Session和RBAC**：

| 入口 | 网络/边缘第一层 | 应用账号密码 | 最终授权依据 |
| --- | --- | --- | --- |
| Cloudflare | Access邮箱/IdP策略 | 必须 | 当前用户的`WorkspaceMembership`与Role |
| 局域网 | 指定网卡、CIDR和主机防火墙 | 必须 | 当前用户的`WorkspaceMembership`与Role |
| ZeroTier | Private网络及已授权设备 | 必须 | 当前用户的`WorkspaceMembership`与Role |

因此正确表述是：

> **局域网和ZeroTier不需要Cloudflare Access这一层前置身份验证，但仍然必须登录应用账号。ZeroTier设备授权和局域网范围限制只是额外的网络防线，不能代替应用用户身份。**

ZeroTier私有网络中的新设备必须由控制器授权后才能通信，设备拥有Managed IP，链路流量使用设备密钥加密；它可以减少应用暴露面，但不能回答“当前是哪一位员工在操作”。([ZeroTier Docs][19])([ZeroTier Docs][20])

局域网的信任更弱。访客Wi-Fi、IoT设备、被入侵的电脑或错误VLAN都可能位于同一网段，所以局域网入口还必须满足：

* 只绑定明确的LAN IP，不监听所有网卡的`0.0.0.0`；
* 明确配置可信CIDR，并由宿主机防火墙再次限制；
* 访客网络、IoT网络和办公网络应分离；
* 不能仅根据客户端提交的`X-Forwarded-For`、`Host`或自定义Header判断它来自局域网；
* 未登录请求统一跳转登录页或返回`401`，不能因为源IP可信而直接建立用户身份。

### 应用账号体系是所有入口的共同安全底座

第一版至少建立：

```text
User
UserCredential
UserSession
WorkspaceMembership
Role / Permission
PasswordResetToken
AuditLog
```

账号安全基线：

* 首次部署只允许通过本机初始化流程创建第一个管理员；
* 默认关闭公开注册，由管理员邀请或创建成员；
* 密码使用Argon2id等面向密码的哈希算法保存，绝不保存可逆明文；
* Session使用`Secure`、`HttpOnly`和合适的`SameSite` Cookie；
* 写操作需要CSRF防护，登录接口需要限速、失败计数和审计；
* 提供一次性恢复码或本机管理员重置流程，不能依赖数据库手工改密码；
* 高风险操作要求重新输入密码，TOTP/Passkey等MFA进入Next；
* Cloudflare入口同时验证Access JWT和应用Session，默认要求Access邮箱与应用账号邮箱一致。

应用应建立统一请求上下文：

```text
RequestContext
    ingress: cloudflare | lan | zerotier
    source_ip
    access_email: optional
    session_user_id
    workspace_membership_id
    roles
    request_id
```

权限建议：

* `viewer`：查看房态、指标和事件详情；
* `operator`：创建或调整预订、清洁、维修等业务事件；
* `workspace_admin`：管理房间、模板、字段和业务成员；
* `security_admin`：管理Cloudflare、ZeroTier、OAuth、Token、备份恢复和删除操作。

不同网络仍然可以配置不同的**权限上限**，但网络只能收紧权限，不能给用户提权：

```text
effective_permissions
    = user_role_permissions
    ∩ ingress_policy_allowed_permissions
```

例如可以规定公网Cloudflare入口不允许执行备份恢复，而局域网或ZeroTier入口允许安全管理员执行；但一个`viewer`绝不会因为从ZeroTier进入就自动变成`operator`。

以下操作在任何入口都要求已登录的`security_admin`，并进行密码重新验证：

* 修改Cloudflare、ZeroTier或网络入口配置；
* 查看、导入或轮换API Token与Refresh Token；
* 连接个人Google/Microsoft账号；
* 修改用户、角色和工作空间安全设置；
* 执行数据导出、恢复、批量删除和审计日志清理。

### 入口必须在网络层分离

不要让同一个监听端口收到请求后再猜测来源。推荐三个独立入口：

```text
public gateway
    只连接cloudflared所在的edge Docker network
    验证Access JWT

lan gateway
    只绑定宿主机指定LAN IP
    清除外部身份Header后标记ingress=lan

zerotier gateway
    只绑定宿主机ZeroTier Managed IP
    清除外部身份Header后标记ingress=zerotier
```

三个Gateway可以是同一个网关程序的三个Listener，但配置、端口、防火墙和边缘验证中间件必须独立。所有Listener最终进入同一个应用登录和Session校验中间件。应用后端只接受来自受信网关的内部签名入口信息，用户身份和角色必须从服务端Session及数据库读取，不能相信浏览器直接传入的角色或入口类型。

### ZeroTier部署方式

ZeroTier网络必须设置为`Private`，新设备逐台批准；遗失或不再使用的设备要及时Deauthorize。ZeroTier官方也建议保持私有网络并定期检查授权成员。([ZeroTier Docs][21])

MVP推荐把ZeroTier One安装在Docker宿主机上：

```text
Docker Host加入既有ZeroTier Private Network
    → 管理员在ZeroTier Central批准该主机
    → 获得ZeroTier Managed IP
    → Compose只把zerotier gateway绑定到该Managed IP
```

不建议第一版把ZeroTier One直接塞进业务Compose。官方容器方案需要`NET_ADMIN`、`SYS_ADMIN`和`/dev/net/tun`，会显著扩大容器权限；宿主机安装能保持业务容器无特权。([ZeroTier Docs][22])

ZeroTier第一版只读取Network ID和服务端Managed IP，不保存ZeroTier Central API Token，也不自动批准客户端设备。自动创建网络、批准成员、Flow Rules和集中设备管理进入Next，并且要使用独立的最小权限部署工具。

建议在ZeroTier侧只允许访问WebUI所需的HTTPS端口，默认不开放PostgreSQL、Redis、Docker API或SSH；不要启用默认路由接管，DNS和Managed Routes也只按需要开启。ZeroTier客户端本身支持分别控制Managed Routes、Default Route和DNS。([ZeroTier Docs][23])

### PWA与HTTPS限制

Cloudflare入口天然提供公网HTTPS。局域网和ZeroTier如果直接使用`http://IP:port`，普通WebUI可以打开，但Service Worker、安装式PWA和部分浏览器能力可能因为不是安全上下文而不可用。

因此完整PWA需要为私网入口增加TLS，优先方案是：

```text
内部域名，例如 calendar.zt.example.com
    → 内部/ZeroTier DNS解析到Managed IP
    → 通过ACME DNS-01获取可信证书
    → zerotier gateway提供HTTPS
```

本地CA也可以使用，但所有手机和电脑都要安装并信任根证书。若暂时只提供HTTP，界面必须明确标记为“基础WebUI模式”，不能宣称完整PWA能力。

---

# 七、入口验证、产品账号和日历授权必须分为三件事

用户感知上可以保持简单，但系统内部必须明确分层。

## 第一层：网络或边缘入口验证

* Cloudflare入口先经过Access邮箱/IdP策略；
* 局域网入口先经过网卡、CIDR和防火墙限制；
* ZeroTier入口先经过Private网络的设备成员授权。

这一层只决定请求能否到达产品登录页，不直接创建应用Session，也不直接授予业务权限。Cloudflare Access可以集成Google、Google Workspace和Microsoft Entra等身份提供商，并把认证结果作为额外的边缘身份传给应用。([Cloudflare Docs][4])

## 第二层：使用产品账号密码登录

所有入口统一显示产品自身的登录页：

```text
邮箱或用户名
密码
登录
```

验证成功后，应用建立服务端Session，并从数据库加载：

```text
User
UserCredential
UserSession
WorkspaceMembership
Role
ViewPreset
```

Cloudflare入口默认要求Access邮箱与应用账号邮箱一致，但Access JWT本身不能替代应用账号密码。未来如果增加Google/Microsoft SSO，应作为明确的账号绑定功能单独设计，不能与日历数据授权混为一体。

## 第三层：授权访问日历

登录产品并不自动意味着产品可以访问外部日历。

用户还需要点击：

```text
连接Google Calendar
连接Microsoft Outlook
```

系统才申请日历权限。

Google推荐Web Server OAuth流程；需要服务器在用户离线时持续同步，应请求`offline`访问，从而获得Refresh Token。Google Calendar也提供不同粒度的日历权限，应采用最小权限原则。([Google for Developers][5])

Microsoft使用授权码流程并配合PKCE；需要后台持续同步时申请`offline_access`，读写日历使用委托权限`Calendars.ReadWrite`，该委托权限同时支持个人Microsoft账户。([Microsoft Learn][6])

第一版推荐只申请日历连接所需权限：

```text
Google日历：
calendar.calendarlist.readonly
calendar.events

Microsoft日历：
offline_access
Calendars.ReadWrite
```

数据库中至少分成三类模型：

```text
IdentityAccount
    可选的Cloudflare Access、Google或Microsoft外部身份映射

UserCredential / UserSession
    产品自身账号密码、会话和安全状态

CalendarConnection
    用于保存日历授权、Refresh Token和同步状态
```

这样一个用户可以：

* 用产品账号密码登录；
* 从Cloudflare入口进入时再经过Access前置验证；
* 同时连接Google日历；
* 再连接两个Microsoft 365账户；
* 以后再连接自己的酒店系统。

---

# 八、Docker部署拓扑

推荐的Docker Compose结构：

```text
Cloudflare Access → cloudflared ──┐
指定LAN IP与防火墙 ────────────────┼→ Entry Gateways
ZeroTier Private Network ─────────┘        │
                                          ▼
                              应用账号密码 + Session + RBAC
                                          │
┌─────────────────────────────────────────▼─┐
│              Docker Private Networks       │
│                                             │
│  calendar-web       React/Vite PWA          │
│  calendar-api       FastAPI业务接口         │
│  calendar-worker    同步、任务、统计         │
│  calendar-sync      Keeper或自研连接器       │
│  postgres           业务数据库              │
│  redis              队列、缓存、事件广播     │
│  webhook-receiver   外部通知接收器           │
└─────────────────────────────────────────────┘
```

Docker网络应进一步拆成：

```text
edge network
    cloudflared ↔ calendar-gateway

app network
    calendar-gateway ↔ calendar-web / calendar-api / webhook-receiver

data network
    calendar-api / calendar-worker / calendar-sync ↔ postgres / redis
```

`cloudflared`不能直接访问PostgreSQL、Redis或内部Worker。开发环境如果需要宿主机访问Web或API，只绑定`127.0.0.1`，生产配置不发布这些端口。

Token模式的Compose骨架可以是：

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:<pinned-version>
    command: tunnel --no-autoupdate run --token-file /run/secrets/cloudflare_tunnel_token
    secrets:
      - cloudflare_tunnel_token
    restart: unless-stopped
    networks:
      - edge

  calendar-gateway:
    expose:
      - "8080"
    networks:
      - edge
      - app
```

镜像版本应固定为支持`--token-file`的`2025.4.0`或更高版本，并由升级流程主动更新，不依赖容器内自动升级。([Cloudflare Docs][18])

核心应用容器使用：

```yaml
expose:
  - "3000"
```

而不是：

```yaml
ports:
  - "3000:3000"
```

即不把Web、API、数据库等核心服务直接发布到宿主机所有网卡。只有启用局域网或ZeroTier入口时，对应Gateway才允许绑定到明确的网卡IP：

```yaml
services:
  lan-gateway:
    ports:
      - "${LAN_BIND_IP}:8443:8443"

  zerotier-gateway:
    ports:
      - "${ZEROTIER_BIND_IP}:8443:8443"
```

禁止使用`0.0.0.0:8443:8443`作为可信网络入口，因为这可能同时暴露到公网网卡、其他VLAN或未预期的Docker网络。

建议至少分两个数据库或Schema：

```text
calendar_app
    业务模板、用户、资源、业务事件

calendar_sync
    外部账户、Token、同步游标、外部事件
```

不要让业务系统直接依赖某个开源同步项目的内部表结构，而应通过其API或自己的适配层调用。

---

# 九、目前最值得利用的开源项目

截至目前，没有一个开源项目能完整覆盖：

* Google和Microsoft双向同步；
* Docker部署；
* Cloudflare Access；
* 酒店房态；
* 工厂设备时间轴；
* 多企业视图；
* 行业模板；
* 用户个性化视图；
* 自有系统连接器。

但可以组合现有项目，把开发量压缩很多。

## 1. Keeper.sh：最接近的同步内核

Keeper.sh目前支持Google Calendar、Outlook、Office 365、iCloud、Fastmail、CalDAV和ICS，并对Google和Outlook使用增量同步；它还提供REST API，可查询、创建、修改和删除事件。([GitHub][7])

它已经包含：

* Google OAuth；
* Microsoft OAuth；
* Token保存；
* 增量同步；
* Worker；
* Cron；
* PostgreSQL；
* Redis；
* REST API；
* Webhook推送；
* Docker镜像；
* 单容器和拆分服务部署。

官方提供`keeper-standalone`和拆分式Docker镜像，单容器中可包含Web、API、Cron、Worker、Redis、PostgreSQL和Caddy，也可以使用外部PostgreSQL和Redis。([GitHub][7])

**适合用途：**

> 把Keeper作为“外部日历同步微服务”，我们的产品负责行业模板和业务呈现。

**不建议：**

> 直接在Keeper现有界面上持续叠加酒店、工厂和企业管理功能。

因为它的主要定位仍然是跨日历聚合与避免重复预约，不是业务资源管理系统。

另外，Keeper采用AGPL-3.0许可证。若以后要做闭源商业产品，应在正式选型前评估修改、部署及服务边界下的许可证义务。([GitHub][7])

## 2. EventCalendar：最适合的开源视觉底座

`vkurko/calendar`的EventCalendar采用MIT许可证，已经提供：

* 月历；
* 周视图；
* 列表；
* Resource Timeline；
* Resource Time Grid；
* 拖拽；
* 调整事件长度；
* 自定义事件内容；
* CSS变量主题。

它的资源时间轴可以直接承载：

* 房间 × 日期；
* 设备 × 时间；
* 产线 × 班次；
* 企业 × 里程碑。

这比重新手写所有日历交互快很多，而且资源时间轴不需要FullCalendar的Premium授权。([GitHub][8])

**推荐定位：**

> EventCalendar负责通用时间轴和交互，我们自行实现今日房态、入住率矩阵、工厂停机看板等高度业务化组件。

## 3. 10xapp/core-oss：适合参考整体架构

这个项目采用Apache-2.0许可证，技术栈包含：

* Python/FastAPI；
* React/Vite；
* Google和Microsoft日历同步；
* 多工作空间；
* RBAC；
* PostgreSQL；
* Google/Microsoft OAuth。

它与你现在倾向的技术路线高度接近。([GitHub][9])

不足是它当前更偏Supabase和Vercel部署，不是可以直接拉起的完整Docker日历产品。因此它适合：

* 参考数据结构；
* 参考FastAPI路由；
* 参考Google和Microsoft同步代码；
* 参考Workspace和RBAC设计。

不适合作为唯一主框架直接改造。

## 4. Cal.diy：适合参考OAuth和连接器

Cal.diy是Cal.com的社区开源版本，采用MIT许可证，包含Google、Microsoft等日历集成，也提供Docker Compose构建方式。([GitHub][10])

但它的核心业务是：

* 预约页面；
* 空闲时间；
* 会议预订；
* 预约类型。

而且其文档明确提示更适合个人、自托管和非生产用途，并移除了Teams、Organizations、SSO等企业能力。([GitHub][10])

因此适合复制或参考：

* OAuth接入流程；
* Provider Adapter；
* Token加密；
* 日历选择；
* Redirect Callback。

不适合作为你的产品主体。

## 5. Frappe：适合重后台、轻前端的备选路线

Frappe提供：

* 管理后台；
* RBAC；
* 自动REST API；
* 自定义表单；
* 自定义视图；
* 报表；
* 官方Docker环境。

如果重点是快速搭建工厂后台、企业表单和权限系统，它能节省大量后台开发。([GitHub][11])

但它的前端体系较重，想实现消费级PWA体验、酒店房态交互和高度定制的时间轴，最终仍然需要单独开发前端。因此不建议把Frappe作为当前产品主框架。

---

# 十、推荐的最终组合

最合理的方案不是Fork某一个大型项目，而是组合：

```text
Cloudflare + Access     可信局域网     ZeroTier Private Network
          └──────────────┼──────────────┘
                  独立入口Gateway
                         │
                  React/Vite PWA
                         │
EventCalendar + 自研行业视图
                         │
FastAPI业务与模板引擎
                         │
PostgreSQL + Redis
                         │
Keeper.sh同步服务
                         │
Google / Microsoft / CalDAV
```

各部分职责明确：

| 组件             | 职责                              |
| -------------- | ------------------------------- |
| Cloudflare     | 域名、TLS、Tunnel、入口鉴权              |
| 可信局域网        | 指定网卡/CIDR内的本地直连入口              |
| ZeroTier       | 已授权设备组成的跨公网私有网络入口             |
| Bootstrap CLI  | 校验参数，幂等创建Tunnel、DNS和Access策略    |
| Entry Gateways | 分离Public/LAN/ZeroTier Listener并生成访问上下文 |
| React PWA      | Mac、Windows、iPad、Android Pad、iPhone、Android统一客户端 |
| EventCalendar  | 月历、列表、资源时间轴、拖拽                  |
| 自研行业组件         | 房态矩阵、运维看板、企业风险视图                |
| FastAPI        | 工作空间、模板、权限、业务规则、系统接口            |
| Keeper         | Google、Microsoft、CalDAV同步       |
| PostgreSQL     | 统一业务数据和模板                       |
| Redis          | 同步任务、缓存、实时通知                    |
| Docker Compose | 整体部署和升级                         |
| Observability  | 日志、审计、Tunnel健康、同步状态、备份恢复       |

但Keeper应先作为独立同步服务验证，不要第一天就深度Fork。

---

# 十一、建议先做四条相互独立的技术验证

正式开发前并行验证“日历同步内核”、“Cloudflare安全部署闭环”、“可信私网入口”和“多端响应式客户端”。它们分别决定同步内核选型、公网部署能力、局域网/ZeroTier安全边界，以及PWA能否成为未来App与桌面封装的共享前端核心。

## A. Calendar Sync Kernel验收

1. Docker部署Keeper；
2. 通过Cloudflare Tunnel访问；
3. Google OAuth连接；
4. Microsoft个人账户连接；
5. Microsoft 365企业账户连接；
6. 全天事件创建、修改和删除；
7. 重复事件和周期事件；
8. Google修改后同步到本地；
9. Outlook删除后同步到本地；
10. 多账户、多日历；
11. 多用户数据隔离；
12. Refresh Token自动刷新；
13. Docker重启后同步状态不丢失；
14. REST API创建和修改事件；
15. Webhook经过Cloudflare独立路径进入；
16. AGPL许可证边界评估。

只有以下硬门槛全部通过，并且其余项目至少80%直接满足，才采用：

* 多用户数据隔离；
* Refresh Token安全保存与自动刷新；
* 创建、修改、删除、周期事件和Webhook同步正确；
* Docker重启后状态不丢失；
* AGPL许可证边界可以接受。

> **Keeper作为Calendar Sync Kernel。**

如果它对多租户、扩展字段或同步控制存在较大限制，就采用：

> **FastAPI自研同步内核，同时参考Keeper、10xapp和Cal.diy的连接器实现。**

## B. Cloudflare安全部署闭环验收

1. 引导器仅输入Account ID、Zone ID、API Token、域名和邮箱列表即可创建或复用Tunnel；
2. 自动生成`hostname → Docker服务:端口`Ingress和代理CNAME；
3. 重复执行引导器不会生成重复Tunnel、DNS记录或Access应用；
4. 指定Gmail地址能通过OTP或Google IdP访问，未授权Gmail地址被拒绝；
5. Cloudflare API Token不会出现在Compose明文、浏览器、数据库或普通日志中；
6. Tunnel断开、Token失效、DNS冲突和Access策略创建失败都有可读诊断与恢复步骤；
7. `calendar.example.com`受Access保护，Webhook与OAuth回调只在精确路径或独立域名开放；
8. 后端拒绝没有有效Access JWT的受保护请求。

这8项属于安全上线门槛，不能用“80%通过”替代。未全部通过时，只允许在本机或测试环境继续开发，不显示“公网访问已安全开放”。

## C. 局域网与ZeroTier可信入口验收

1. 局域网Gateway只绑定指定LAN IP和可信CIDR，不监听`0.0.0.0`；
2. ZeroTier网络保持Private，只有已授权成员能连接服务端Managed IP；
3. 未批准或已Deauthorize的ZeroTier设备无法访问WebUI；
4. Public、LAN、ZeroTier三个Listener不能通过伪造Header互相冒充；
5. LAN和ZeroTier上的未登录请求仍然被登录页或`401`阻止；
6. 同一应用账号从三个入口进入时都执行相同的Session与RBAC校验；
7. 日志能记录入口、用户、角色、源IP和请求ID，形成个人级审计；
8. 局域网与ZeroTier使用HTTPS时完整PWA可安装；只使用HTTP时界面正确降级为基础WebUI。

这8项同样属于安全门槛。尤其不能只检查源IP、ZeroTier成员资格或客户端可提交的Header，就绕过应用账号登录。

## D. 多端响应式PWA验收

1. iPhone Safari和主屏PWA完成登录、房态查看、事件编辑与OAuth回跳；
2. Android Chrome和安装式PWA完成相同主流程；
3. iPad和Android Pad在横竖屏切换后布局、筛选和编辑状态不丢失；
4. Desktop Web在高密度时间轴下支持鼠标、键盘、筛选和详情面板；
5. 除时间轴自身外不存在页面级意外横向滚动，触控操作不依赖Hover或右键；
6. Service Worker不缓存登录、私有API、Token或用户数据响应；
7. 弱网、断网、同步中、同步失败和重试状态在所有终端都有明确反馈；
8. 前端不直接依赖桌面专属API，平台能力全部通过`ClientPlatformAdapter`访问。

这8项通过后，才认为当前Web前端具备进入iOS/Android App或DMG/EXE封装验证的基础。

---

# 十二、第一版产品范围应控制住

第一版不应该同时完整实现酒店、工厂、企业三套产品。

正确方式是：

## 底层从第一天支持模板

先建设：

```text
Resource
TimelineEvent
TemplateDefinition
ViewPreset
FieldMapping
ConnectorBinding
```

## 产品层先完整实现酒店模板

因为酒店场景最容易验证模板化价值：

* 全天事件；
* 房间资源；
* 日期占用；
* 状态颜色；
* 入住率；
* 快速新增；
* 移动端查看；
* 与外部日历同步。

## 工厂和企业先做概念模板

只验证：

* 相同底层数据模型能否承载；
* 是否可以更换Resource；
* 是否可以更换状态；
* 是否可以更换视图；
* 是否可以更换指标和快速表单。

等酒店模板跑通，再完整开发工厂和企业版本。

---

# 十三、轻量路线图

## Now：当前MVP必须完成

* 冻结酒店经营者/店长这一主用户和房态管理这一主场景；
* 建立`Resource`、`TimelineEvent`、`TemplateDefinition`和`ViewPreset`最小数据模型；
* 用EventCalendar跑通房间资源时间轴；
* 交付手机、Pad和Desktop三档响应式布局以及可安装PWA；
* 建立`ClientPlatformAdapter`，隔离OAuth回跳、通知、文件和生命周期等平台能力；
* Docker Compose启动Web、API、数据库、Worker和独立入口网关，按需启用`cloudflared`；
* 支持Cloudflare、局域网和既有ZeroTier私网的组合式入口配置；
* 部署引导器在启用Cloudflare时幂等创建Tunnel、DNS、Access应用和精确邮箱Allow策略；
* 支持应用账号密码、Session、RBAC、Access JWT双层校验、个人审计日志和本地备份；
* 使用模拟数据完成PWA端到端验证；
* 完成Keeper是否适合作为同步内核的技术验证。

## Next：MVP跑通后的下一轮

* Google Calendar和Microsoft Calendar双向同步；
* 酒店模板的今日入住、离店、维修、待清洁和7/14天指标；
* 管理员在本地控制台维护邮箱白名单，并安全地Reconcile到Cloudflare；
* ZeroTier Central API自动建网、成员审批辅助、Flow Rules和设备状态同步；
* TOTP、Passkey、恢复码和高风险操作的Step-up Authentication；
* ZeroTier设备状态作为可选的附加安全信号，但不替代应用用户身份；
* 局域网/ZeroTier内部域名、DNS-01证书和私网HTTPS自动续期；
* 个人视图预设、基础工作空间角色、Token轮换、定时备份和恢复演练；
* `cloudflared`多副本、健康告警和升级流程；
* PWA推送、离线只读快照、离线Outbox和移动端操作优化；
* iOS/Android客户端外壳以及DMG/EXE桌面外壳的兼容性Spike。

## Later：先进入想法池

* 正式发布iOS和Android App；
* 正式发布带签名、自动更新的macOS DMG与Windows EXE客户端；
* 工厂、企业管理、门店预约等完整行业模板；
* 可视化模板编辑器和模板市场；
* 多租户SaaS、复杂权限矩阵、计费和支付；
* AI自动排期、冲突解释、经营摘要和自然语言创建事件；
* WARP私网访问、设备姿态和更高级的Zero Trust策略；
* 通用内网服务发布控制台；仅在完成独立安全模型、端口白名单和审计设计后评估。

## Risk：必须先验证或持续控制

* Keeper的AGPL许可证边界以及多用户隔离能力；
* Google/Microsoft Refresh Token的加密、撤销和恢复；
* 多源双向同步中的冲突、重复事件、周期事件和删除语义；
* Cloudflare API权限过大、Token泄漏或错误策略导致意外公网开放；
* 局域网中访客、IoT或被入侵设备可以到达登录面，导致密码喷洒或漏洞探测；
* ZeroTier已授权设备丢失、多人共用或密钥泄漏后，攻击者仍可能尝试应用账号登录；
* Cloudflare Access身份与应用账号不一致，造成共享账号或跨身份登录；
* Access身份与应用内部用户、工作空间成员关系不一致；
* PWA在Access登录、Cookie、后台同步和离线缓存上的兼容性；
* iOS PWA、Android PWA和桌面浏览器对安装、通知、后台生命周期支持不一致；
* 页面只按桌面设计后再缩放，导致Pad和手机无法完成高频房态操作；
* OAuth在Standalone PWA或未来原生外壳中的外部浏览器回跳丢失应用状态；
* 备份不可恢复、Docker升级失败和单机故障；
* 过早同时开发酒店、工厂和企业模板导致MVP失焦。

---

# 最终产品定义

这套产品可以定义为：

> **一个可以把Google Calendar、Microsoft Outlook及企业业务系统统一连接起来，并通过行业模板和个人视图，将时间数据转换为酒店房态、工厂运维、企业经营等业务视图的跨端时间管理平台。**

第一阶段技术方案确定为：

> **Cloudflare Tunnel/Access、可信局域网、ZeroTier私网三种可组合入口 + Docker Compose + 面向Phone/Pad/Desktop的响应式React/Vite PWA + EventCalendar + FastAPI模板业务层 + PostgreSQL/Redis + Keeper.sh同步技术验证，并为后续iOS/Android及DMG/EXE客户端外壳保留平台适配层。**

这条路线可以最大程度复用现有开源能力，同时把真正需要自主掌握的部分集中在“行业模板、业务资源模型、个性化视图和自有系统连接器”上。

[1]: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/ "https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/"
[2]: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/ "https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/"
[3]: https://developers.cloudflare.com/cloudflare-one/access-controls/policies/common-policies/ "https://developers.cloudflare.com/cloudflare-one/access-controls/policies/common-policies/"
[4]: https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/entra-id/ "https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/entra-id/"
[5]: https://developers.google.com/identity/protocols/oauth2/web-server "https://developers.google.com/identity/protocols/oauth2/web-server"
[6]: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow "https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow"
[7]: https://github.com/ridafkih/keeper.sh "https://github.com/ridafkih/keeper.sh"
[8]: https://github.com/vkurko/calendar "https://github.com/vkurko/calendar"
[9]: https://github.com/10xapp/core-oss "https://github.com/10xapp/core-oss"
[10]: https://github.com/calcom/cal.diy "https://github.com/calcom/cal.diy"
[11]: https://github.com/frappe/frappe "https://github.com/frappe/frappe"
[12]: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel-api/ "Create a tunnel (API)"
[13]: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/ "Publish a self-hosted application to the Internet"
[14]: https://developers.cloudflare.com/cloudflare-one/access-controls/policies/ "Access policies"
[15]: https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/ "One-time PIN login"
[16]: https://developers.cloudflare.com/fundamentals/api/reference/permissions/ "API token permissions"
[17]: https://developers.cloudflare.com/tunnel/advanced/tunnel-tokens/ "Tunnel tokens"
[18]: https://developers.cloudflare.com/tunnel/advanced/run-parameters/ "Tunnel run parameters"
[19]: https://docs.zerotier.com/quickstart/ "ZeroTier Quickstart and device authorization"
[20]: https://docs.zerotier.com/security/ "ZeroTier Security"
[21]: https://docs.zerotier.com/enterprise-deployment/ "ZeroTier Enterprise Deployment Guide"
[22]: https://docs.zerotier.com/docker/ "ZeroTier in Docker"
[23]: https://docs.zerotier.com/config/ "ZeroTier Client Configuration"
