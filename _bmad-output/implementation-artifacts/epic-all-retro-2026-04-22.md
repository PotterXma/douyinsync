# DouyinSync 全项目总回顾
# Epic 1 + Epic 2 + Epic 3 — 首次正式回顾

**日期**: 2026-04-22  
**范围**: Epic 1（零触碰同步管道）+ Epic 2（管道防护与调度）+ Epic 3（可见性与控制中心）  
**参与者**: Project Lead、Amelia（开发）、Alice（产品）、Charlie（高级工程师）、Dana（QA）、Elena（初级工程师）

---

## 交付指标

| 维度 | 结果 |
|------|------|
| Story 完成率 | **13/13（100%）** |
| 技术债遗留（交付后） | **0 条**（2 条已于本次回顾前全部清零） |
| 测试文件数 | **13 个**，覆盖全部核心模块 |
| 关键 NFR 达成 | WAL 并发、流式下载 < 50MB 内存、非阻塞 UI 轮询 |

---

## Epic 2 专项复盘（Project Lead 重点标记）

### 最具挑战的 Story

**Story 2.2（APScheduler 调度引擎）** — 评选为全项目最高复杂度 Story。

- **核心难点**：`BackgroundScheduler`（同步）与 `asyncio` 管道（异步）的跨线程互操作，最终通过 `asyncio.run_coroutine_threadsafe()` 方案解决。
- **其他难点**：非重叠执行锁（threading.Lock）确保调度不重叠，以及 APScheduler 优雅关机序列。

**Story 2.1（熔断器 + 重试装饰器）**

- `@auto_retry` 和 `@circuit_breaker` 需要同时支持 `async` 和 `sync` 函数，设计时应提前决定双模式支持，而非事后追加。
- PST 午夜时区计算（`_get_seconds_until_midnight_pst`）是隐蔽的跨时区陷阱。

**Story 2.3（日志脱敏轮转）**

- `LogSanitizer` 注入时机问题：必须在 `main.py` 最开始全局挂载，晚于部分模块初始化则会有早期日志漏出。

---

## 跨 Epic 重复出现的问题模式

### 问题 1 — Async/Sync 边界模糊（出现于 3+ Story）

**现象**：下载器、调度器、Dashboard 均在 async/sync 互操作处踩坑，测试套件使用 `AsyncMock` 时多次写法错误。  
**根因**：项目初期未明文规定各层的 async/sync 归属。  
**行动项 A1**：在 `project-context.md` 中补充"async/sync 分层边界"规则。

### 问题 2 — Mock 测试样板重复（出现于 5+ Story）

**现象**：在 `patch` 上下文外执行 `import` 导致 Mock 不生效，每个 Story 重新踩雷。  
**根因**：缺少统一的 Mock 工厂规范文档和 `conftest.py` 共享 fixtures。  
**行动项 A2**：新增 `tests/conftest.py`，提供通用 Mock 工厂，减少重复 patch 样板。

### 问题 3 — PyInstaller 路径样板重复（出现于 4 个模块）

**现象**：`sys.frozen` 判断逻辑在 `database.py`、`config_manager.py`、`sweeper.py`、`scheduler.py` 中各写一次。  
**根因**：没有提前抽象成工具函数。  
**行动项 A3**：将路径逻辑抽取至 `utils/paths.py`，所有新模块统一引用。

### 问题 4 — 异常分层不足（代码审查反复出现）

**现象**：YouTube Uploader、Downloader、Notifier 初版均用单个 `except Exception` 掩盖不同类型错误，代码审查阶段才发现。  
**行动项**：在 Story 验收标准中显式要求"分层异常处理"，Blind Hunter 代码审查中作为必查项。

---

## 做得好的地方

| 主题 | 具体表现 |
|------|---------|
| **韧性设计贯穿始终** | 熔断器、重试、zombie 恢复、午夜竞态修复，全部有回归测试覆盖 |
| **测试文化从 Day 1 建立** | Epic 1 第一个 Story 就配套测试，后续 Epic 自然延续 |
| **单向数据流严格执行** | UI 层全程零违规，无一处 UPDATE/INSERT |
| **技术债透明化** | deferred-work.md 全程追踪，回顾时全部清零 |
| **代码审查制度有效** | 三层 CR（Blind Hunter / Edge Case Hunter / Acceptance Auditor）捕获了多个隐患 |

---

## 行动项清单

### 流程改进

| # | 行动 | 负责人 | 执行时机 |
|---|------|--------|---------|
| A1 | `project-context.md` 新增 async/sync 分层边界规则 | 架构师 | Epic 4 开始前 |
| A2 | 新增 `tests/conftest.py` 统一 Mock 工厂 | 开发工程师 | Epic 4 Story 1 之前 |
| A3 | 抽取 `utils/paths.py` 统一 PyInstaller 路径逻辑 | 开发工程师 | Epic 4 首个新模块时 |

### 技术债（✅ 已全部清零）

- ~~`poll_db` 同步阻塞 `mainloop`~~ → Story 3.4 以 `.after()` 非阻塞轮询解决
- ~~`push_daily_summary` 午夜滚动竞态~~ → 本次引入 `_snapshot_and_reset_daily_counter()` 修复，3 个回归测试通过

---

## Epic 4 准备事项

**前置条件（必须在 Epic 4 Story 1 开始前完成）：**

- [ ] **A1** — 补充 `project-context.md` async/sync 边界规则
- [ ] **A2** — 创建 `tests/conftest.py` 共享 Mock 工厂
- [ ] **A3** — 创建 `utils/paths.py` 统一路径工具函数

**Epic 4 相关规划文档**：`_bmad-output/implementation-artifacts/epic-4-context.md`

---

## 回顾结论

**DouyinSync v1.0 全量交付**。项目从单一配置管理器起步，历经 3 个 Epic 13 个 Story，建立了完整的视频搬运自动化系统，包含：

- **零触碰同步管道**（抖音抓取 → 下载 → YouTube 上传）
- **生产级韧性基础设施**（重试/熔断/崩溃自愈/磁盘管理）
- **完整可见性层**（系统托盘 + iOS 推送 + CTk HUD 仪表盘）

技术债归零，文档完整，测试套件绿灯。项目已具备开启 Epic 4 的条件。
