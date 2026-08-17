import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import styles from "./oauth-guide.module.css";

export const metadata: Metadata = {
  title: "日历连接与同步图文教程 · Auto Calendar",
  description: "Google Calendar 与 Microsoft Calendar 的 OAuth 注册、自动创建专用日历、选择同步范围和环境变量配置教程。",
};

const localGoogleCallback = "http://localhost:8080/api/oauth/google/callback";
const localMicrosoftCallback = "http://localhost:8080/api/oauth/microsoft/callback";

function Code({ children }: { children: React.ReactNode }) {
  return <code className={styles.inlineCode}>{children}</code>;
}

function Shot({ src, alt, caption, width, height }: { src: string; alt: string; caption: string; width: number; height: number }) {
  return <figure className={styles.shot}>
    <div className={styles.shotFrame}><Image src={src} alt={alt} width={width} height={height} sizes="(max-width: 760px) 94vw, 1120px" /></div>
    <figcaption>{caption}</figcaption>
  </figure>;
}

export default function OAuthGuidePage() {
  return <main className={styles.page}>
    <header className={styles.hero}>
      <nav className={styles.topNav} aria-label="教程导航">
        <Link href="/?view=connections">← 返回日历连接</Link>
        <span>Auto Calendar · 管理员教程</span>
      </nav>
      <div className={styles.heroCopy}>
        <p className={styles.eyebrow}>只在第一次部署时配置</p>
        <h1>连接 Google 与 Microsoft<br />并选择自动同步日历</h1>
        <p>先为 Auto Calendar 登记一张“应用身份证”，再让你本人在供应商网页授权自己的日历。授权完成后，可以直接在本系统一键创建云端专用日历，或选择已有日历作为同步目标。</p>
        <div className={styles.heroActions}>
          <a href="#google">配置 Google</a>
          <a href="#microsoft">配置 Microsoft</a>
          <a href="#address">选择 localhost 或公网</a>
          <a href="#sync-calendar">创建 / 选择同步日历</a>
        </div>
      </div>
    </header>

    <section className={styles.content}>
      <article className={styles.callout}>
        <strong>先记住：Client ID 不是回调 URL，Client Secret 也不是 Secret ID。</strong>
        <p>供应商生成 Client ID/Secret；Auto Calendar 生成 callback。三者用途不同，必须放到各自位置。Microsoft 参数来自 Microsoft Entra（Azure）的 App registrations，不来自 Microsoft Teams。</p>
      </article>

      <section className={styles.overviewGrid} aria-label="OAuth 配置总览">
        <article><span>01</span><strong>登记应用</strong><p>在 Google Cloud 或 Microsoft Entra 创建 Web 应用。</p></article>
        <article><span>02</span><strong>登记 callback</strong><p>把 Auto Calendar 显示的完整回调地址复制到供应商后台。</p></article>
        <article><span>03</span><strong>绑定 .env</strong><p>把供应商生成的 Client ID 和 Client Secret 保存到服务器。</p></article>
        <article><span>04</span><strong>重启并授权</strong><p>重启服务，在 WebUI 点击连接并登录你自己的日历账号。</p></article>
      </section>

      <section className={styles.providerSection} id="google">
        <div className={styles.sectionHead}>
          <div className={`${styles.providerMark} ${styles.google}`}>G</div>
          <div><p className={styles.eyebrow}>Google Calendar</p><h2>创建 Google OAuth Web Client</h2></div>
          <a className={styles.officialLink} href="https://console.cloud.google.com/" target="_blank" rel="noreferrer">打开 Google Cloud Console ↗</a>
        </div>

        <ol className={styles.steps}>
          <li><strong>选择项目并启用 API</strong><p>打开 Google Cloud Console，在顶部项目选择器中创建或选择用于 Auto Calendar 的项目，然后在 <a href="https://console.cloud.google.com/apis/library/calendar-json.googleapis.com" target="_blank" rel="noreferrer">Google Calendar API 页面</a>点击 Enable。OAuth 客户端和 API 必须属于同一个项目。</p></li>
          <li><strong>完成 Google Auth Platform</strong><p>进入 <Code>Google Auth Platform</Code>，依次确认 Branding、Audience 和 Data Access。个人测试选择 External / Testing，并在 Audience → Test users 中加入实际用于授权的 Gmail，否则会出现 <Code>Error 403: access_denied</Code>。</p></li>
          <li><strong>创建 Web 客户端</strong><p>打开 Clients → Create client，Application type 选择 <Code>Web application</Code>，名称可填写 Auto Calendar。</p></li>
        </ol>

        <Shot src="/tutorials/oauth/google-clients.png" width={2018} height={840} alt="Google Auth Platform Clients 页面，标出 Create client" caption="Google Auth Platform → Clients → Create client。已有客户端时也可以点击名称继续编辑。" />

        <ol className={styles.steps} start={4}>
          <li><strong>填写本地地址</strong><p>Authorized JavaScript origins 填 <Code>http://localhost:8080</Code>，这里不能带路径，也不要以斜杠结尾。Authorized redirect URIs 填完整 callback：<Code>{localGoogleCallback}</Code>。</p></li>
          <li><strong>复制两个凭据</strong><p>页面右侧复制 Client ID 与 Client secret。不要把 callback URL 填进 Client ID，也不要把凭据写进前端代码。</p></li>
        </ol>

        <Shot src="/tutorials/oauth/google-client-settings.png" width={3608} height={2256} alt="Google OAuth Web Client 设置页，标出 origin、redirect URI、Client ID 与 Client secret" caption="Google 客户端详情：左侧登记 origin/callback；右侧取得 Client ID 与 Client secret。截图中的值仅用于示意，请复制你自己项目生成的完整值。" />

        <div className={styles.envCard}>
          <div><span>写入服务器 .env</span><strong>Google 参数绑定</strong></div>
          <pre>{`GOOGLE_CLIENT_ID='Google 页面生成的 Client ID'
GOOGLE_CLIENT_SECRET='Google 页面生成的 Client secret'`}</pre>
        </div>
        <p className={styles.note}>Google 应用处于 Testing 时，只有 Test users 能授权；带 Calendar 等非基础权限的测试授权可能在 7 天后失效。个人 MVP 先用测试模式跑通，正式开放用户前再处理发布与验证。</p>
      </section>

      <section className={styles.providerSection} id="microsoft">
        <div className={styles.sectionHead}>
          <div className={`${styles.providerMark} ${styles.microsoft}`}>M</div>
          <div><p className={styles.eyebrow}>Microsoft Calendar / Outlook</p><h2>创建 Microsoft Entra App Registration</h2></div>
          <a className={styles.officialLink} href="https://portal.azure.com/" target="_blank" rel="noreferrer">打开 Microsoft Azure Portal ↗</a>
        </div>

        <article className={styles.namingNote}>
          <strong>不是 Microsoft Teams 参数</strong>
          <p>需要的是 Azure Portal → Microsoft Entra ID → App registrations 生成的 <Code>Application (client) ID</Code> 和 Client secret <Code>Value</Code>。Teams、Object ID、Directory ID 和 Secret ID 都不能填到对应的 Client 参数中。</p>
        </article>

        <ol className={styles.steps}>
          <li><strong>进入应用注册</strong><p>打开 Azure Portal，搜索 Microsoft Entra ID，进入 App registrations，然后点击 New registration。</p></li>
          <li><strong>选择账号范围</strong><p>只同步 Outlook/Hotmail/MSN 个人账号时选择 <Code>Personal accounts only</Code>；如果还要支持企业/学校 Microsoft 365 账号，选择组织目录与个人账号组合选项。</p></li>
          <li><strong>登记 Web 回调</strong><p>Platform 选择 <Code>Web</Code>，本地测试填写 <Code>{localMicrosoftCallback}</Code>，然后完成注册。</p></li>
        </ol>

        <Shot src="/tutorials/oauth/microsoft-app-registrations.png" width={2506} height={2250} alt="Microsoft Entra App registrations 页面，标出 New registration 与 Auto Calendar" caption="Microsoft Entra ID → App registrations → New registration。创建后点击 Auto Calendar 进入详情。" />

        <ol className={styles.steps} start={4}>
          <li><strong>复制 Application (client) ID</strong><p>Overview 页面复制 <Code>Application (client) ID</Code>，填入 <Code>MICROSOFT_CLIENT_ID</Code>。不要复制 Object ID 或 Directory (tenant) ID。</p></li>
          <li><strong>创建 Client secret</strong><p>Certificates & secrets → Client secrets → New client secret。创建完成后立即复制 <Code>Value</Code>，填入 <Code>MICROSOFT_CLIENT_SECRET</Code>。不要复制右侧 UUID 格式的 <Code>Secret ID</Code>；Value 离开页面后通常不能再次完整查看。</p></li>
          <li><strong>添加委托权限</strong><p>API permissions → Microsoft Graph → Delegated permissions，加入 <Code>User.Read</Code>、<Code>Calendars.ReadWrite</Code> 和 <Code>offline_access</Code>。这里使用 Delegated permissions，因为是用户本人授权自己的日历。</p></li>
        </ol>

        <Shot src="/tutorials/oauth/microsoft-overview.png" width={2970} height={1660} alt="Microsoft Entra 应用 Overview 页面，标出 Application client ID 与 Client credentials" caption="Overview：左侧 Application (client) ID 对应 MICROSOFT_CLIENT_ID；右侧 Client credentials 进入密钥页面。截图中的标识仅用于示意。" />

        <div className={styles.tenantTable}>
          <div className={styles.tableTitle}><span>最容易踩坑的参数</span><strong>MICROSOFT_TENANT 应该填什么？</strong></div>
          <div className={styles.tableRow}><Code>consumers</Code><p>推荐用于你当前的 Personal accounts only 应用，只允许 Outlook/Hotmail/MSN 等个人 Microsoft 账号。</p></div>
          <div className={styles.tableRow}><Code>common</Code><p>用于“组织目录 + 个人 Microsoft 账号”的多账号类型应用。Personal accounts only 配合 common 会返回 userAudience 错误。</p></div>
          <div className={styles.tableRow}><Code>Directory tenant ID</Code><p>用于限定某一个企业/学校 Entra 租户，不适合当前只同步个人 MSN 账号的配置。</p></div>
        </div>

        <div className={styles.envCard}>
          <div><span>个人 Microsoft 账号方案</span><strong>Microsoft 参数绑定</strong></div>
          <pre>{`MICROSOFT_CLIENT_ID='Application (client) ID'
MICROSOFT_CLIENT_SECRET='Client secret 的 Value'
MICROSOFT_TENANT=consumers`}</pre>
        </div>
      </section>

      <section className={styles.providerSection} id="address">
        <div className={styles.sectionHead}>
          <div className={`${styles.providerMark} ${styles.address}`}>↗</div>
          <div><p className={styles.eyebrow}>回调地址</p><h2>localhost 与公网 HTTPS 怎么选？</h2></div>
        </div>
        <div className={styles.addressGrid}>
          <article><span>纯本机测试</span><h3>localhost 可以正常回调</h3><p>浏览器和 Auto Calendar 都运行在同一台电脑时，Google/Microsoft 可以把浏览器送回 localhost。它不是公网地址，但本机测试完全有效。</p><pre>{`SOURCE_PUBLIC_BASE_URL=http://localhost:8080
SESSION_COOKIE_SECURE=false`}</pre></article>
          <article><span>VPS / 异地用户</span><h3>必须使用固定公网 HTTPS 域名</h3><p>可用 Cloudflare Tunnel 或 Nginx Proxy Manager 将域名转发到 WebUI 8080。不要直接把 FastAPI 8000 暴露到公网。</p><pre>{`PUBLIC_BASE_URL=https://calendar.example.com
SOURCE_PUBLIC_BASE_URL=https://calendar.example.com
SESSION_COOKIE_SECURE=true`}</pre></article>
        </div>
        <p className={styles.note}>修改域名后，Google 和 Microsoft 后台的 redirect URI 也必须换成同一个域名，并与 Auto Calendar 页面显示的 callback 逐字一致。</p>
      </section>

      <section className={styles.providerSection} id="sync-calendar">
        <div className={styles.sectionHead}>
          <div className={`${styles.providerMark} ${styles.address}`}>↔</div>
          <div><p className={styles.eyebrow}>授权后的自动同步选择器</p><h2>一键创建或选择专用日历</h2></div>
        </div>
        <article className={styles.namingNote}>
          <strong>是的，“创建专用日历”会直接创建到你的云端账号</strong>
          <p>点击 Google 卡片中的按钮，日历会建立在当前已授权的 Google Calendar 账号中；点击 Microsoft 卡片中的按钮，则会建立在当前已授权的 Outlook / Microsoft 365 账号中。创建成功后，Auto Calendar 会自动保存并选中它，无需再去官方日历手工建立。</p>
        </article>

        <Shot src="/tutorials/sync/automatic-calendar-selector.png" width={1891} height={831} alt="Auto Calendar 日历连接页，标出 Google 与 Microsoft 的创建专用日历按钮" caption="自动同步日历选择器：填写名称后点击“创建专用日历”，系统会直接在已授权账号中创建真实的云端日历，并自动把它设为当前同步目标。图中的账号信息已隐去。" />

        <div className={styles.selectorFlow} aria-label="自动同步日历设置步骤">
          <article><span>01</span><strong>连接账号</strong><p>先完成 Google 或 Microsoft OAuth，卡片右上角应显示“已连接”。</p></article>
          <article><span>02</span><strong>建立同步边界</strong><p>推荐填写 <Code>Auto Calendar · 酒店订房</Code>，再点击“创建专用日历”。</p></article>
          <article><span>03</span><strong>或选择已有日历</strong><p>如果已经有专用日历，点击“选择已有日历”并从供应商返回的列表中选择；不要误选个人主日历。</p></article>
          <article><span>04</span><strong>选择同步方向</strong><p>保存双向、只读、只写或暂停，并按需要设置分类 / 标识。</p></article>
          <article><span>05</span><strong>开始同步</strong><p>“立即同步”处理当前供应商；页面顶部“同步全部日历”会协调 Google、Auto Calendar 与 Microsoft。</p></article>
        </div>

        <div className={styles.addressGrid}>
          <article><span>创建专用日历（推荐）</span><h3>系统自动创建并选中</h3><p>适合第一次配置。它创建的是供应商账号里的真实日历，不是本地 tag。创建完成后“立即同步”会自动启用，你也能在 Google / Outlook 中单独显示、隐藏或改颜色。</p></article>
          <article><span>选择已有日历</span><h3>复用你已经建立的日历</h3><p>适合已有“酒店订房”等业务日历的情况。选择后，只有该日历进入当前连接的同步范围；个人主日历和其他日历不会自动混进来。</p></article>
          <article><span>同步方向</span><h3>决定数据可以往哪里流动</h3><p><strong>双向</strong>：官方日历 ↔ Auto Calendar；<strong>只读</strong>：官方日历 → Auto Calendar；<strong>只写</strong>：Auto Calendar → 官方日历；<strong>暂停</strong>：保留授权但不读写。</p></article>
          <article><span>分类 / 标识</span><h3>用于辨认，不是匹配通道</h3><p>Outlook 会显示分类名称，Google 使用隐藏扩展属性标记事件。真正避免重复、识别同一事件的是服务器端映射记录，不是两个平台恰好使用相同名称。</p></article>
        </div>
        <div className={styles.faq}>
          <details open><summary>为什么“立即同步”还是灰色？</summary><p>尚未创建或选择同步目标时按钮会禁用。先点“创建专用日历”，或用“选择已有日历”选定一个日历；成功保存后按钮即可使用。</p></details>
          <details><summary>需要先到 Google 或 Outlook 手工创建吗？</summary><p>不需要。最简单的路径就是直接使用 Auto Calendar 的“创建专用日历”。只有你想复用一个已经存在的日历时，才需要点击“选择已有日历”。</p></details>
          <details open><summary>为什么日历 ID 和 tag 不写进 .env？</summary><p><Code>.env</Code> 只保存部署级 OAuth Client ID / Secret。选择哪个日历、双向还是只读、使用什么分类，都是每个登录用户自己的设置，会安全地保存在数据库。</p></details>
          <details><summary>四种同步模式如何选择？</summary><p><strong>双向</strong>用于三端连续同步；<strong>只读</strong>只把官方日历导入 Auto Calendar；<strong>只写</strong>只把酒店事件发布出去；<strong>暂停</strong>保留连接但停止同步。</p></details>
          <details><summary>为什么 Google 创建专用日历提示权限不足？</summary><p>旧 Google 授权令牌可能没有“管理日历”权限。现在直接再次点击“创建专用日历”即可：系统会自动打开 Google 补充授权，返回后自动继续完成刚才的创建操作。也可以使用卡片底部的“重新授权 Google”。</p></details>
        </div>
      </section>

      <section className={styles.providerSection} id="troubleshooting">
        <div className={styles.sectionHead}><div><p className={styles.eyebrow}>排错清单</p><h2>刚才实际遇到的常见问题</h2></div></div>
        <div className={styles.faq}>
          <details><summary>按钮是灰色，提示 OAuth 未配置</summary><p>检查对应 Client ID 与 Client Secret 是否为空。Client ID 不能填写 callback URL。保存 <Code>.env</Code> 后必须重启当前运行方式。</p></details>
          <details><summary>Google 显示 Error 403: access_denied</summary><p>应用仍在 Testing，但当前 Gmail 没有加入 Audience → Test users。添加实际登录账号后重新授权。</p></details>
          <details><summary>提示 Google Calendar API has not been used or is disabled</summary><p>OAuth 已连接不代表 Calendar API 已启用。打开 <a href="https://console.cloud.google.com/apis/library/calendar-json.googleapis.com" target="_blank" rel="noreferrer">Google Calendar API</a>，确认顶部选中创建 OAuth Client 的同一个项目，点击 Enable，等待几分钟后重试。</p></details>
          <details><summary>Microsoft 授权后直接返回，仍显示未连接</summary><p>如果日志出现 userAudience 与 /common 不匹配：Personal accounts only 使用 <Code>MICROSOFT_TENANT=consumers</Code>；组织目录 + 个人账号应用才使用 <Code>common</Code>。</p></details>
          <details><summary>Provider rejected the authorization code</summary><p>最常见原因是把 Secret ID 当作 Secret Value。重新创建 Client secret，复制 Value，替换 <Code>MICROSOFT_CLIENT_SECRET</Code>，重启后从 WebUI 发起一次全新的授权。</p></details>
          <details><summary>redirect_uri_mismatch</summary><p>供应商后台登记的 callback 与应用实际发送的地址不完全一致。检查协议、域名、端口、路径和末尾斜杠。</p></details>
        </div>
      </section>

      <section className={styles.finish}>
        <div><p className={styles.eyebrow}>保存配置后</p><h2>重启服务，再回到连接页授权</h2></div>
        <div className={styles.commandGrid}><pre>{`# 源码模式
./scripts/manage-source.sh restart`}</pre><pre>{`# Docker 模式
./scripts/manage.sh build`}</pre></div>
        <Link href="/?view=connections">返回 Auto Calendar 日历连接 →</Link>
      </section>
    </section>
  </main>;
}
