# Emby-CC (Emby Community Care) - 项目计划书

## 一、项目背景

### 1.1 项目起源

emby-keeper 是一个优秀的 Emby 社区维护工具，提供自动签到、保号（keepalive）、Telegram 机器人签到等功能。作者使用半年多，整体体验良好，但存在以下核心问题：

- **作者停止维护**：核心开发者已基本不更新代码
- **认证服务器断连**：依赖的 auth 服务器不可用，导致大量功能异常
- **Emby API 兼容性差**：4.8+ 版本的 AdditionalParts 等新接口报 404
- **Telegram Bot 签到不稳定**：多个 bot 签到失败，社区无人修复
- **代码架构陈旧**：部分代码缺乏异常处理，错误恢复机制薄弱

### 1.2 Emby-CC 定位

Emby-CC（Emby Community Care）定位为 emby-keeper 的现代化替代品，**核心功能是签到和保活**，同时提供丰富的增强能力。水群、抢注等社交/抢夺类功能暂不开发。

**核心功能**：
1. **签到** — Telegram Bot 自动签到 + Emby 站点签到
2. **保活** — Emby 账号播放模拟，防止账号被回收

**核心原则**：
- 模块化设计，易于维护和扩展
- 完善的错误处理和自动恢复机制
- 兼容 Emby 4.6 ~ 4.9+ 全版本
- 简单可靠，开箱即用

---

## 二、emby-keeper 架构分析

### 2.1 优点（Emby-CC 需要保留）

| 特性 | 说明 |
|------|------|
| Telegram Bot 签到 | 支持多种 TG bot 自动签到 |
| Emby 保号 | 自动播放时长模拟，防止账号被回收 |
| 多账号管理 | TOML 配置文件管理多个 Emby 账号 |
| Docker 部署 | Docker 镜像一键启动 |
| 智能播放 | 模拟真实播放行为 |

### 2.2 缺点（Emby-CC 需要优化）

| 问题 | 详情 | Emby-CC 解决方案 |
|------|------|------------------|
| 异常处理薄弱 | API 调用失败直接崩溃 | 全局 try/except + 指数退避重试 |
| Emby API 不兼容 | 4.8+ 新接口 404 未捕获 | 版本检测 + 降级兼容层 |
| 认证服务依赖 | 依赖外部 auth 服务器 | 本地认证 + 备用认证源 |
| 配置不灵活 | 硬编码 bot 列表 | 插件化 bot 注册机制 |
| 日志不清晰 | 错误信息难以排查 | 结构化日志 + 可视化仪表盘 |
| 无健康检查 | 无法主动发现异常 | 内置 HTTP 健康检查端点 |

---

## 三、Emby-CC 技术架构

### 3.1 技术栈

```
Python 3.11+
├── httpx + curl_cffi    # HTTP 请求（TLS 指纹模拟）
├── Telethon             # Telegram API
├── lxml + cssselect     # HTML 解析
├── SQLAlchemy + aiosqlite # 异步数据存储
├── Rich                 # 终端美化输出
├── Click / Typer        # CLI 框架
└── (可选) Playwright    # 浏览器签到支持
```

### 3.2 项目结构

```
emby-cc/
├── pyproject.toml
├── README.md
├── LICENSE                  # MIT
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── src/
│   └── emby_cc/
│       ├── __init__.py
│       ├── __main__.py      # CLI 入口
│       ├── config.py        # 配置加载（TOML + 热更新）
│       ├── core/
│       │   ├── emby_client.py    # Emby API 客户端（版本兼容层）
│       │   ├── auth.py           # 认证模块
│       │   ├── scheduler.py      # 任务调度器（签到 + 保活）
│       │   ├── keepalive.py      # 保活模块（播放模拟）
│       │   └── health.py         # 健康检查端点
│       ├── plugins/
│       │   ├── __init__.py       # 插件注册机制
│       │   ├── base.py           # 签到插件基类
│       │   └── telegram/
│       │       ├── base.py       # TG Bot 签到基类
│       │       ├── zyfb.py       # ZYFX Bot
│       │       ├── csbot.py      # CSBot
│       │       ├── checkbot.py   # CheckBot
│       │       ├── embybot.py    # EmbyBot
│       │       └── ptbot.py      # PTBot
│       ├── ai/
│       │   ├── __init__.py       # AI 签到模块入口
│       │   ├── ocr.py            # OCR 识别（验证码等）
│       │   └── llm.py            # LLM 辅助签到（复杂交互）
│       ├── browser/
│       │   ├── __init__.py       # 浏览器签到模块
│       │   └── playwright.py     # Playwright 驱动
│       ├── web/
│       │   ├── __init__.py
│       │   └── dashboard.py      # Web 仪表盘
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── models.py         # 数据模型
│       │   └── stats.py          # 数据统计
│       └── utils/
│           ├── logger.py         # 结构化日志
│           ├── retry.py          # 重试装饰器
│           └── tls.py            # TLS 指纹工具
└── tests/
    ├── test_config.py
    ├── test_emby_client.py
    └── test_plugins/
```

### 3.3 Emby API 兼容层设计

```python
class EmbyClient:
    """支持 Emby 4.6 ~ 4.9+ 的兼容客户端"""

    def __init__(self, base_url, api_key, username):
        self.base_url = base_url.rstrip('/')
        self.headers = {'X-Emby-Token': api_key}
        self._server_version = None

    async def detect_version(self):
        """自动检测 Emby 服务器版本"""
        info = await self._get('/System/Info/Public')
        self._server_version = info.get('Version', '4.7.0.0')
        return self._server_version

    async def get_additional_parts(self, user_id):
        """带降级的 AdditionalParts 获取"""
        try:
            return await self._get(f'/Users/{user_id}/AdditionalParts')
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return await self._fallback_user_info(user_id)
            raise

    async def simulate_playback(self, item_id, duration_minutes=30):
        """模拟播放行为 - 保活核心"""
        ...
```

### 3.4 插件系统设计（签到）

```python
class CheckinPlugin:
    """签到插件基类"""
    name: str = 'base'
    description: str = ''
    enabled: bool = True

    @abstractmethod
    async def checkin(self, account: Account) -> CheckinResult:
        """执行签到，返回成功/失败"""
        pass

    def should_run(self, account: Account, schedule: Schedule) -> bool:
        """判断是否应该执行"""
        return self.enabled and schedule.is_due(self.name)


class TelegramCheckinPlugin(CheckinPlugin):
    """Telegram Bot 签到插件基类"""
    bot_username: str = ''

    @abstractmethod
    async def send_checkin_message(self, client: TelegramClient) -> bool:
        pass


class BrowserCheckinPlugin(CheckinPlugin):
    """浏览器签到插件基类（基于 Playwright）"""
    login_url: str = ''

    async def checkin(self, account: Account) -> CheckinResult:
        # 自动登录 -> 点击签到按钮 -> 截图确认
        ...
```

### 3.5 保活模块设计

```python
class KeepAliveRunner:
    """Emby 账号保活"""

    async def run(self, account: Account):
        """执行一次保活循环"""
        # 1. 随机选取媒体项
        item = await self._random_item(account)
        # 2. 模拟播放指定时长
        duration = random.randint(
            account.keepalive_min_minutes,
            account.keepalive_max_minutes
        )
        await account.emby.simulate_playback(item.id, duration)
        # 3. 标记为已播放
        await account.emby.mark_played(item.id, account.user_id)
        # 4. 记录统计
        await stats.record_play(account.name, item.name, duration)
        logger.info(f'[{account.name}] 保活完成: {item.name} ({duration}min)')
```

---

## 四、功能规划

### 4.1 P0 - 核心功能（MVP）

| 功能 | 说明 |
|------|------|
| Emby 多账号管理 | TOML 配置，支持导入导出 |
| Emby 保号 | 智能播放模拟，随机片源 |
| 基础签到 | Emby 站点内置签到 |
| TG Bot 签到 | 至少支持 5 个高频 bot |
| 自动重试 | 指数退避 + 最大重试次数 |
| Docker 部署 | docker-compose 一键启动 |

### 4.2 P1 - 重要增强

| 功能 | 说明 |
|------|------|
| 插件系统 | 第三方可开发签到插件 |
| Emby API 兼容层 | 4.6 ~ 4.9+ 全版本兼容 |
| 结构化日志 | JSON 日志 + 按级别归档 |
| 健康检查端点 | HTTP API 暴露运行状态 |
| 失败通知 | TG/邮件/Webhook 通知 |
| 数据统计 | 签到成功率、播放时长统计 |

### 4.3 P2 - 高级功能

| 功能 | 说明 |
|------|------|
| Web 仪表盘 | 可视化查看签到/保号状态 |
| 配置热更新 | 不重启加载新配置 |
| AI 辅助签到 | LLM 处理验证码/复杂交互 |
| 浏览器签到 | Playwright 支持需要浏览器的签到 |
| 分布式部署 | Redis/MQ 多实例协调 |
| OCR 验证码 | 自动识别图片验证码 |

---

## 五、配置文件设计

```toml
[general]
version = "1.0.0"
log_level = "info"
health_port = 8080
# 配置热更新（P2）
hot_reload = false
hot_reload_interval_seconds = 60

[auth]
server = "https://your-auth-server.com"
# 备用认证源
fallback_server = "https://backup-auth.com"
timeout = 30

[notifications]
enabled = true
type = "telegram"
bot_token = ""
chat_id = ""
# 仅在失败时通知
notify_on = ["error", "warning"]

[[accounts]]
name = "主力号"
emby_url = "https://emby.example.com"
username = "admin"
password = "***"
api_key = "your-api-key"
telegram_bot_token = ""

# 保号设置
[accounts.keepalive]
enabled = true
interval_hours = 6
min_minutes = 30
max_minutes = 120

# 签到设置
[accounts.checkin]
telegram_bots = ["zyfxbot", "csbot", "checkbot"]

[[accounts]]
name = "小号1"
emby_url = "https://emby2.example.com"
username = "user1"
password = "***"
api_key = "key2"

[accounts.keepalive]
enabled = true
interval_hours = 12
min_minutes = 20
max_minutes = 60

[accounts.checkin]
telegram_bots = ["zyfxbot"]

[dashboard]
enabled = false
port = 8081

[distributed]
enabled = false
backend = "sqlite"
```

---

## 六、开发里程碑

### 第 1-2 周：基础框架

- [ ] 项目脚手架搭建（pyproject.toml, 项目结构）
- [ ] 配置加载模块（TOML 解析 + 校验）
- [ ] Emby API 客户端（基础版 + 版本检测）
- [ ] 日志模块（Rich 美化输出）
- [ ] CLI 框架（Click/Typer）

### 第 3-4 周：核心功能

- [ ] Emby 保号模块（播放模拟 + 标记已播放）
- [ ] Emby 站点签到
- [ ] TG Bot 签到框架 + 5 个 bot 实现
- [ ] 自动重试机制（指数退避）
- [ ] 多账号管理

### 第 5-6 周：稳定性 & 部署

- [ ] Emby 4.6-4.9+ 兼容层
- [ ] 异常处理完善 + 失败通知
- [ ] Docker 镜像构建
- [ ] 健康检查端点
- [ ] 单元测试覆盖

### 第 7-8 周：增强功能

- [ ] 数据统计模块（签到/保活记录）
- [ ] Web 仪表盘
- [ ] 配置热更新
- [ ] AI 辅助签到（LLM + OCR）
- [ ] 浏览器签到（Playwright）

### 第 9-10 周：高级 & 发布

- [ ] 分布式部署支持（Redis）
- [ ] 端到端测试
- [ ] 完善文档 + 使用指南
- [ ] 首次发布 v1.0.0

---

## 七、TG 签到 Bot 优先级

| # | Bot | 说明 | 难度 |
|---|-----|------|------|
| 1 | ZYFX Bot | 最主流的 Emby 签到 Bot | 低 |
| 2 | CSBot | 社区签到 Bot | 低 |
| 3 | CheckBot | 通用签到 | 低 |
| 4 | EmbyBot | Emby 官方风格 | 中 |
| 5 | PTBot | PT 站签到 | 中 |

---

## 八、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| Emby API 变更 | 签到/保活失效 | 版本兼容层 + 快速适配 |
| TG Bot 规则变更 | 签到逻辑失效 | 插件化设计，独立更新单个 bot |
| 认证服务器不可用 | 无法获取 Token | 多认证源 + 本地缓存 |
| 被 Emby 站点封禁 | 账号被封 | 随机延迟 + 行为模拟 |
| 代码维护负担 | 长期维护困难 | 良好的架构 + 社区贡献 |

---

## 九、开源策略

- **许可证**：MIT License
- **代码托管**：GitHub
- **版本管理**：语义化版本（SemVer）
- **发布周期**：每 2 周一个 Patch，每月一个 Minor
- **贡献指南**：CONTRIBUTING.md + Issue 模板

---

## 十、与 emby-keeper 的对比

| 维度 | emby-keeper | Emby-CC |
|------|-------------|---------|
| 核心功能 | 签到+保活+水群+抢注 | 签到+保活（精简专注） |
| 维护状态 | 停更 | 持续更新 |
| 错误处理 | 基础 | 完善（重试+降级） |
| Emby 兼容 | 4.7 为主 | 4.6 ~ 4.9+ |
| 插件系统 | 无 | 有（可扩展） |
| 日志系统 | 基础 print | 结构化 + 可视化 |
| 通知机制 | 有限 | TG/邮件/Webhook |
| 数据统计 | 无 | 有 |
| 健康检查 | 无 | HTTP 端点 |
| AI 签到 | 无 | 有（LLM + OCR） |
| 浏览器签到 | 无 | 有（Playwright） |
| 部署方式 | Docker | Docker + 裸机 + 分布式 |
| 配置格式 | TOML | TOML（热更新） |

---

*文档版本：v1.2 | 更新日期：2026-06-02*
*变更：保留 AI 签到/浏览器签到/分布式/仪表盘/统计/热更新，仅移除水群和抢注*
