---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments: []
workflowType: 'architecture'
project_name: 'DouyinSync'
user_name: 'Administrator'
date: '2026-04-19'
lastStep: 8
status: 'complete'
completedAt: '2026-04-19'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
系统由一条纯后台异步管道（Pipeline）与一个提供观测/调度的控制台构成。要求支持分离代理网络请求、防并发的本地 SQLite 状态流转、大文件流式 YouTube API 上传，以及基于 Bark 的全流程事件通报。

**Non-Functional Requirements:**
架构极其注重资源控制与自防御态势。最高优先级的 NFR 包括：I/O 获取锁的退避机制以防止资源抢占、限制所有下载和传输必须走 Stream I/O 阻断内存膨胀（控制大文件峰值在 300MB 内），以及必须配置硬盘耗尽自检（>=2GB可用）和未处理网络异常的日志级别自动脱敏。

**Scale & Complexity:**
- Primary domain: 本地守护进程 / 数据处理管道 (Local Daemon / Pipeline)
- Complexity level: Medium-High (极强的异常状态恢复与边界防御要求)
- Estimated architectural components: 约 5-7 个核心模块 (调度引擎、爬虫、存储、上传、日志清理、托盘 UI)

### Technical Constraints & Dependencies

- 必须复用/借鉴姐妹项目 `youtebe搬运` 现有的 Notifier/Database 抽象架构。
- 必须通过 `Pillow` 等方式实现本地静默的格式转化并维护过期流媒体文件的 GC（垃圾回收清理）。
- 数据库层必须开启 `PRAGMA journal_mode=WAL;` 进一步消除跨线程读写死锁。

### Cross-Cutting Concerns Identified

- **网络分流中心 (Split-Tunneling)**：统一拦截外发请求并分开实例化 HTTP Client 会话（Douyin 直连，YouTube 过代理池）。
- **全局状态熔断器**：处理并拦截由于配额溢出或安全验证引发的管道暂停，避免死循环消耗尝试次数。
- **僵尸任务回滚与硬盘防雪崩**：应用启动强制抹除 processing 悬挂态；在每次媒体下载前动态断言 `disk_usage`。
- **全局日志脱敏拦截网**：必须保护敏感 Cookie/Token 数据在调试层不发生本地落地。

## Starter Template Evaluation

### Primary Technology Domain

Desktop Daemon App Pipeline (基于 Python)

### Starter Options Considered

1. **Standard Cookiecutter PyPackage**: 适用于通用 CLI 工具，但不符合纯后台守护进程的特殊需求。
2. **Textual/Rich 终端模板**: 适用于 TUI，但我们要依托系统托盘（pystray）做隐式桌面交互，不需要重度依赖终端控制台。
3. **Custom "youtebe搬运" Modular Architecture**: 完全复用前项目提炼的模块化架构心法，确保双向搬运生态互通与代码库轻量。

### Selected Starter: Custom "youtebe搬运" Modular Pipeline

**Rationale for Selection:**
基于 PRD 所确立的 MVP 策略，此项目必须且已经在代码级别（`modules/` 目录）对姐妹系统进行严谨复用。我们不引入任何不必要的外部结构生成器，而是直接采用原生的 Python VirtualEnvironment + APScheduler + SQLite 结合业务逻辑搭建。

**Initialization Command:**

```bash
# 依赖文件已生成，直接安装即可
pip install -r requirements.txt
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
- Python 3.10+ (强制支持 httpx 异步 I/O 及强类型提示 Type Hinting)。

**Styling/UI Solution:**
- 无复杂的图形渲染引擎依赖。由 `pystray` 托盘栏和作为远期规划的轻量 Dashoboard 负责呈现。
- **解耦声明**：UI 线程必须与后台 Pipeline 解耦，仪表盘仅以非加锁只读模式轮询查询 Database 状态；严禁在 UI 线程内部直接发起密集阻塞型网络 I/O。

**Build Tooling & Optimization:**
- 免配置。未来生产发布版将通过 `PyInstaller` 静态构建无头执行文件（.exe）。

**Testing Framework:**
- `pytest` 与 `pytest-asyncio`（以 TDD 为引导线，要求单测必须完全穿透异常回滚逻辑与状态机）。

**Code Organization:**
- 模块深度解耦划分（强制遵循控制反转注入设计模式 DI，拒绝模块间的死代码耦合读取，提升横向迁移测试能力）：
  - `modules/config_manager.py`
  - `modules/database.py` (自带 WAL 高并发防锁读写设置)
  - `modules/douyin_fetcher.py`
  - `modules/downloader.py`
  - `modules/youtube_uploader.py`
  - `modules/notifier.py`

**Development Experience:**
- 依托内置标准库。业务级 debug 借由 `logging` 模块配合 Sanitizer 脱敏层自动剔除 Cookie 与凭据参数。

**Note:** 该初始化层级环境已就绪，首个开发冲刺 (Sprint) 将直接基于此根目录进行代码填充。

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data Pattern: DAO 仓储模式。
- Resilience Pattern: Decorator-based Circuit Breaker & Retry 拦截器。

**Important Decisions (Shape Architecture):**
- UI Communication Pattern: Python `queue.Queue` 进程内指令通讯同步。

**Deferred Decisions (Post-MVP):**
- 无显著推迟决议。完整的架构与 UI 通讯链已打通。

### Data Architecture

- **Decision**: DAO Repository (数据访问对象接口封装)。
- **Version**: 原生 Python `sqlite3`。
- **Rationale**: 阻断所有的 SQL 分散硬编码注入，所有的 DB 流转收口在 `AppDatabase` 类中调用操作。同时在初始化建立连接池时开启 WAL 预写日志。
- **Affects**: `database.py` 以及所有的爬取、推送模块的调用格式。

### Authentication & Security

- **Decision**: 全局拦截的脱敏器 (Log Sanitizer Filter)。
- **Version**: 原生 Python `logging` 拓展。
- **Rationale**: 必须从底层将 Cookie/Bearer Token 打码，不落盘。
- **Provided by Starter**: Yes（作为模块化内部分享的规定）。

### API & Communication Patterns

- **Decision**: 无侵入的异常捕获装饰器 (`@auto_retry`, `@circuit_breaker`)
- **Rationale**: 将三次失败退避重试 (Exponential Backoff) 及 403 熔断硬切离具体的网络抓取方法外，做到零侵入业务。

### Frontend Architecture (UI IPC & GUI Framework)

- **Decision**: 使用 `CustomTkinter` 原生构建，与内核共生；采用“主线程运行 GUI + 后台子线程跑 Pipeline”的并发模型。
- **Rationale**: 
  - **框架抉择**: 抛弃重量级的 FastAPI+Vue 组合。CustomTkinter 完全符合内存 <100MB 的 NFR 要求，且能被 PyInstaller 完美打包为单体 `.exe`。
  - **IPC 与状态解耦 (State Sync)**: 
    - **下行 (UI -> Pipeline)**: 托盘与 Dashboard 的指令动作（如 `[重载]`、`[重试]`）作为生产者，通过进程内的 `queue.Queue` 下发非阻塞事件。
    - **上行 (Pipeline -> UI)**: 废弃了试图用回调刷新界面的脏逻辑。Dashboard 只采用只读单向轮询（每 3 秒执行一次只读的 SQLite `SELECT`），以获取最新状态并批量更新 `[Pipeline-Status-Card]`。
- **Affects**: `main.py` 的入口组装逻辑生变（必须拦截主线程给 `CustomTkinter.mainloop()`），并在 `ui/dashboard_app.py` 中引入 `.after()` 定时查询器。

### Decision Impact Analysis

**Implementation Sequence:**
1. Database DAO 层 (防锁底层)
2. Common Utilities (重试与熔断装饰器、脱敏日志层)
3. API Clients层 (隔离直连与代理双通道)
4. Scheduler & Queue Controller (调度中枢)

**Cross-Component Dependencies:**
核心业务层完全不依赖 UI。托盘 UI 是按需加载和剥离的。API 互不影响。隔离的 Queue 通道使得未来替换 Dashboard（如 Web Server 代替 Tkinter）变得极其容易。

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
存在 5 个关键的智能体代码冲突区：参数与返回值的封装格式（Dict还是Dataclass？）、日志记录语句（f-string 惰性问题）、SQLite 表与列名大小写、以及 API 重定义错误。

### Naming Patterns

**Database Naming Conventions:**
- 所有表名和列名 **必须是纯小写字母及下划线组合 (snake_case)**。
- 绝不允许使用 `CamelCase` 的列。
- **例子**: `table: videos`, `column: douyin_id`, `column: video_desc`。
- SQLite 时间格式强制采用 ISO-8601 String 或 Unix Timestamp (Integer)，不允许原生 `datetime` 隐式转换。

**Code Naming Conventions:**
- **Variables/Functions**: `snake_case` (e.g., `fetch_user_videos`)
- **Classes**: `PascalCase` (e.g., `DouyinFetcher`, `AppDatabase`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`)

### Structure Patterns

**Project Organization:**
- 工具类 (Utils)：统一维护在 `utils/` 目录下（如 `sanitizer.py`, `decorators.py`）。
- 服务提供者 (Providers)：置于 `modules/` 目录下。
- 前端入口与资源：放置于 `ui/` 目录。

### Format Patterns

**Data Exchange Formats:**
- **内部状态流转约束**：禁止在各组件间直接传递 `dict`，必须使用 Python 的 `@dataclass` 进行强类型实体化（如 `VideoPayload`, `QueueMessage`）。

**Queue Message Format:**
- Queue 通信实体范式：
  `@dataclass class AppEvent: command: str; payload: dict`

### Process Patterns

**Error Handling Patterns:**
- 禁止裸调用 `except Exception:`。网络及重试相关的捕获必须明确为特定业务基类错误 (如 `NetworkTimeoutError`, `YoutubeQuotaError`)。
- 当抛出明确错误时判断是否触发全局熔断或级联退避。

**Logging Guidelines:**
- **日志插值约束**：禁止在传递给 Log 时使用 f-string 执行渲染。
  使用延迟传参机制：`logger.info("Token %s", token)`，确保 Sanitizer 层有机会剔除隐私节点。

### Enforcement Guidelines

**All AI Agents MUST:**
- 必须包含完备的 Type Hinting 签名 (`def execute(self, event: AppEvent) -> bool:`)
- 必须优先从 `modules/config_manager.py` 或依赖注入获取系统参数。严禁散落于文件内部硬编码。

### Pattern Examples

**Good Examples:**
```python
# 符合规范的日志与数据传输
@dataclass
class VideoTask:
    video_id: str
    status: str

def process_video(task: VideoTask) -> None:
    logger.debug("Starting task for video: %s", task.video_id)
```

**Anti-Patterns:**
```python
# 违规的字典注入与提前渲染日志
def processVideo(taskDict):
    logging.debug(f'Starting task {taskDict["id"]}')
```

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
douyin搬运/ (Project Root)
├── README.md                 # 项目运行指南与环境变量要求
├── requirements.txt          # Python 包依赖约束
├── config.json               # 本地持久化配置项（含代理/账户）
├── main.py                   # 启动入口点，组装 Scheduler, Queue 和 UI
├── modules/                  # 核心业务组件
│   ├── __init__.py
│   ├── config_manager.py     # 获取并解析 config.json
│   ├── database.py           # 唯一持有 SQLite connection / WAL 写入锁的 DAO
│   ├── scheduler.py          # 串联调度引擎，内置 queue.Queue 的消费者逻辑
│   ├── douyin_fetcher.py     # 处理抖音反爬/直连拉取主页
│   ├── downloader.py         # 流式下载组件，带文件体积验证 (NFR9) 和 WebP 转换
│   ├── youtube_uploader.py   # 处理 YouTube OAuth 及过代理的大文件推送
│   └── notifier.py           # Bark PUSH 通知中间件
├── utils/                    # 横向支持设施库 (纯函数/拦截器)
│   ├── __init__.py
│   ├── decorators.py         # 存放 @auto_retry 和 @circuit_breaker
│   ├── env_check.py          # 启动时的环境变量及 2GB 空间断言
│   ├── models.py             # 存放全局 Dataclass，如 VideoPayload
│   └── sanitizer.py          # 存放 logging 的 Filter 实现，剔除敏感 token
├── ui/                       # 解耦的可视化与系统交互层
│   ├── __init__.py
│   ├── tray_icon.py          # 基于 pystray 的托盘，向 Queue 发出信号
│   └── dashboard_app.py      # （远期）基于 Tkinter / Web 的轮询只读面板
├── tests/                    # TDD 单测与并发压力测试
│   ├── __init__.py
│   ├── conftest.py           # 共享 pytest fixtures（如模拟 SQLite DB）
│   ├── test_douyin_api.py
│   ├── test_db_locks.py      # 测试高并发写入时不越权
│   ├── test_resilience.py    # 测试熔断装饰器和软硬睡眠机制
│   └── test_sanitizer.py
└── logs/                     # 自动轮转日志输出目录 (运行时创建)
```

### Architectural Boundaries

**API Boundaries:**
- 所有通过 `httpx` 发出的外部请求，必须在 `douyin_fetcher` 和 `youtube_uploader` 两个类中进行。
- 只有对应的 API 类可以进行 Cookie / Bearer Token 的组装与拼接，不允许对外裸露身份凭证对象。
- 两者必须隔离实例化自己的 `AsyncClient` 实例，以独立维持其 HTTP 代理状态（Split-Tunneling）。

**Component Boundaries:**
- UI 层完全单向依赖：`ui/tray_icon.py` 可以发事件到 Queue，但严禁 `ui` 试图阻塞等待处理结果。UI 取最新状态只能轮询 `database.py`。
- `scheduler.py` 作为调度大总管，不跨界触碰底层 Socket。负责实例化各个模块并拼接基于 Python `asyncio` 的处理核心。

**Data Boundaries:**
- 只有 `modules/database.py` 允许发起 `sqlite3.connect()`。
- 不允许任何业务代码模块中出现以 `UPDATE` / `INSERT` 开头的字面量。
- SQLite 库的初始化只允许在应用启动的主线程或唯一的 Worker 线程执行。

### Requirements to Structure Mapping

**Feature/Epic Mapping:**
- 【FR1-2, FR3 全局与分离代理设定】 -> `config.json` 与 `modules/config_manager.py`
- 【FR5-7, FR10, FR16 去重与存储流】 -> `modules/douyin_fetcher.py` + `modules/database.py`
- 【FR21 系统托盘界面】 -> `ui/tray_icon.py`
- 【NFR1-2 大文件与流式下载】 -> `modules/downloader.py` (包含异步 asyncio 执行视频/封面抓取逻辑)
- 【NFR8 日志轮转与隐匿】 -> `main.py(配置 logging)` + `utils/sanitizer.py`

### File Organization Patterns

**导入约束 (Absolute Imports Only):**
- **严禁使用相对导入** (`from ..modules import database`)，整个项目中任何文件的 import 必须从根级绝对路径声明，如 `from modules.database import AppDatabase`，彻底消灭 `ImportError` 陷阱。

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
原生 Python `queue.Queue` 事件传递与底层的 `SQLite3` (并发 WAL) 构成的内部驱动管道逻辑极度协调。`httpx` 的异步并发 I/O 可以完全适配这种无需外围服务组件 (Redis/MQ) 的闭环微架构体系。

**Pattern Consistency:**
所有的代码规范（尤其是禁止字典级传递，使用 `@dataclass` 以及绝对路径 `import` 规范），完美规避了松散微内核结构可能导致的隐性变量污染和跨端测试崩塌。

**Structure Alignment:**
目录按组件功能硬切（`douyin_fetcher`, `youtube_uploader` 等），确保各自网络逻辑与依赖不互相污染，UI 只通过 DB 取数据，结构 100% 支撑架构初衷。

### Requirements Coverage Validation ✅

**Epic/Feature/FR Coverage:**
完全覆盖 PRD 中所有的管道抓取、代理独立配置，以及最终落后的 Bark 重试机制等关键功能需求。

**Non-Functional Requirements Coverage:**
- **NFR 内存天花板**：依赖 `downloader.py` 中的 Async 迭代写盘实现。
- **NFR 断言防雪崩 (Disk 2GB)**：环境检查脚本在 `utils/env_check.py` 完成生命周期拦截。
- **NFR 日志隐私合规**：通过 `utils/sanitizer.py` 中的自定义 Filter 达到 Debug 的安全性。

### Implementation Readiness Validation ✅

**Decision Completeness:**
每个关键决策被记录且约束了相关的防腐层（如 `DAO` 的唯一性）。开发路线清晰，并且全面适配了未来的水平多平台扩展。

**Structure Completeness:**
物理层文件树已经全部罗列。未来所有的 AI subagent 均能明确自己的代码块应插入至何处。

### Validation Issues Addressed
1. **网络与抓取混合阻塞阻塞的问题 (已修复)**：已明确声明 API 层的方法均为非阻塞 Async 协程调用。
2. **测试模块找不到挂载点的坑 (已修复)**：引入强制 Absolute Import 规范消除了导入风暴风险。

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined

**✅ Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**✅ Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION
**Confidence Level:** HIGH (基于已完全验证过的姐妹项目 youtebe搬运 的逻辑衍生，成功把握极大)

**Key Strengths:**
极轻量、自包含、强稳定、容错及状态拉平机制完善，达到开箱即用的常驻守护级别。

**Areas for Future Enhancement:**
核心监控 Dashboard 现已基于 `CustomTkinter` 敲定。未来可增加更多基于统计分析的图形化图表（如 `matplotlib` 嵌入），但当前需死守性能底线。

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions

**First Implementation Priority:**
建立项目基础模块设施：首先完成 `modules/config_manager.py`，并紧跟着实现核心 SQLite DAO 封装 `modules/database.py` (带 WAL)，以此搭建起系统最基础的数据流通层。
