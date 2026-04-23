# 架构设计文档

> **最后更新**: 2026-04-24 | **版本**: v1.1.1（下载/上传失败重试与 BMAD Story 3.4 对齐）

---

## 1. 系统概述

DouyinSync 是一个 **Windows 后台守护进程**，实现抖音视频→YouTube 的自动化搬运管道。采用 **单体架构**，通过 SQLite 状态机解耦各处理阶段，使用 APScheduler 驱动定时任务。

```
┌─────────────────────────────────────────────────────────────┐
│                    DouyinSync 守护进程                        │
│                                                             │
│  ┌──────────┐    ┌─────────────────────────────────────┐    │
│  │ main.py  │───►│         PipelineCoordinator          │   │
│  │ 入口点   │    │         (scheduler.py / APScheduler) │   │
│  └──────────┘    └──────────────┬──────────────────────┘    │
│                                 │ 每 30 分钟触发             │
│               ┌─────────────────┼─────────────────┐         │
│               ▼                 ▼                 ▼         │
│        ┌────────────┐  ┌──────────────┐  ┌──────────────┐  │
│        │  Douyin    │  │  Downloader  │  │   YouTube    │  │
│        │  Fetcher   │  │  下载器      │  │   Uploader   │  │
│        └──────┬─────┘  └──────┬───────┘  └──────┬───────┘  │
│               │               │                 │           │
│               └───────────────▼─────────────────┘           │
│                        SQLite (WAL)                          │
│                     douyinsync.db                            │
│                                                             │
│  ┌────────────┐    ┌────────────┐    ┌────────────────────┐  │
│  │  SystemTray│    │  Dashboard │    │  BarkNotifier      │  │
│  │  (PyStray) │    │ (CTk HUD)  │    │  (iOS Push)        │  │
│  └────────────┘    └────────────┘    └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心数据流

```
抖音用户页面
     │
     ▼ DouyinFetcher（a_bogus 签名 + Cookie）
   视频列表（MP4 URL + WebP 封面 URL）
     │
     ▼ VideoDAO.insert_video_if_unique()
   SQLite: status=pending
     │
     ▼ Downloader（stream iter_content，低内存）
   本地 downloads/  status=downloaded
   + Win OCR 生成 JPEG 封面
     │
     ▼ YoutubeUploader（OAuth + resumable MediaFileUpload）
   YouTube 频道  status=uploaded
```

### 数据流约束

- **单向只读原则**：UI 层只从 SQLite 读取，**永不执行 UPDATE/INSERT**
- **状态机幂等**：所有状态转换通过 `douyin_id` 主键保证唯一性
- **无内存传递**：各组件间不传递对象引用，仅通过 DB 状态协作

---

## 3. 组件架构

### 3.1 管道协调器（PipelineCoordinator）

**文件**: `modules/scheduler.py`

- 使用 `APScheduler.BackgroundScheduler` 在独立线程中每 N 分钟触发一次
- **并发防护**: `threading.Lock` 确保不重叠执行
- **启动序列**:
  1. `VideoDAO.revert_zombies()` — 崩溃自愈
  2. `DiskSweeper.check_preflight_space()` — 磁盘预检
  3. `DiskSweeper.purge_stale_media()` — 清理旧文件
  4. `DouyinFetcher.fetch_all()` — 抓取新视频
  5. `Downloader.process_pending()` — 下载队列
  6. `YoutubeUploader.upload_queue()` — 上传队列

### 3.2 抖音抓取器（DouyinFetcher）

**文件**: `modules/douyin_fetcher.py`

- 伪装 Windows Chrome 指纹（UA、Headers）
- 使用 `abogus.py` / `xbogus.py` 计算 `a_bogus` 请求签名
- 过滤非 MP4 内容（图文 Tuwen 帖）
- CDN 链接过期自动刷新（403 → 重抓 → `update_fresh_urls`）

### 3.3 状态管理（AppDatabase + VideoDAO）

**文件**: `modules/database.py`

- SQLite WAL 模式支持读写并发（UI 轮询 vs 管道写入）
- `busy_timeout=10000ms` 避免锁争用崩溃
- 全部访问通过 `AppDatabase.get_connection()` 上下文管理器
- **禁止**: 在 `database.py` 之外直接 `sqlite3.connect()`

### 3.4 下载器（Downloader）

**文件**: `modules/downloader.py`

- `iter_content(chunk_size=8192)` 流式下载，内存占用 < 50MB
- 集成 `WinOCR` 提取封面文字，叠加到 JPEG 封面
- 代理隔离：通过 `ConfigManager.get_proxies()` 统一注入

### 3.5 YouTube 上传器（YoutubeUploader）

**文件**: `modules/youtube_uploader.py`

- Google OAuth 2.0 鉴权（`token.json` 持久化刷新令牌）
- `MediaFileUpload(resumable=True)` 分块续传
- 配额超限（HTTP 403 QuotaError）触发 `@circuit_breaker`，等待至次日 PST 零时
- 自定义缩略图上传（`thumbnails().set()`）

### 3.6 桌面 UI 层

| 组件 | 文件 | 职责 |
|------|------|------|
| 系统托盘 | `ui/tray_icon.py` + `modules/tray_app.py` | PyStray 图标、右键菜单 |
| HUD 仪表盘 | `ui/dashboard_app.py` | CustomTkinter 实时状态面板 |
| 设置面板 | `modules/ui_settings.py` | 配置调整 UI |
| 统计视图 | `modules/ui_stats.py` | 历史数据展示 |

**UI 线程规则**：
- Dashboard 使用 `root.after(3000, poll_db)` 非阻塞轮询（绝不使用 `time.sleep`）
- 系统托盘点击事件通过 `AppEvent` 传递，不直接调用管道函数

### 3.7 韧性基础设施

| 组件 | 文件 | 机制 |
|------|------|------|
| 指数退避重试 | `utils/decorators.py` | `@auto_retry` |
| 配额熔断器 | `utils/decorators.py` | `@circuit_breaker` |
| 日志脱敏轮转 | `utils/logger.py` + `utils/sanitizer.py` | RotatingFileHandler + Token 过滤 |
| 磁盘自动清理 | `modules/sweeper.py` | 7 天保留期（可配置） |

---

## 4. 韧性设计

### 4.1 崩溃自愈

```
启动时检测 processing/downloading → 重置为 pending
启动时检测 uploading → 重置为 downloaded
连续失败 ≥ 3 次 → 标记为 give_up_fatal（终态）
```

### 4.2 网络容错

```
抖音 CDN 403 → 自动重抓新 URL → 继续下载
YouTube 限流 → @auto_retry(max_retries=3, backoff=指数)
YouTube 配额超限 → @circuit_breaker → 休眠至次日
```

### 4.3 下载与上传失败（管道内）

**文件**: `modules/scheduler.py`、`modules/database.py`

| 场景 | 行为 |
|------|------|
| 下载失败（`download_media` 空或异常） | `retry_count < 3` → **`pending`**、清空本地路径、下周期重试；否则 **`give_up`** + Bark |
| 下载成功 | 写入 **`downloaded`** 且 **`retry_count = 0`**，与上传重试解耦 |
| 上传失败（空 `yt_id` / 非配额异常） | **`failed`** 且保留本地路径，经 `get_uploadable_videos` 在 Phase 3-Pre 重传；满 3 次 → **`give_up`** + Bark |
| 配额超限 | 保持 **`downloaded`**，24h 断路器 |

BMAD：`_bmad-output/implementation-artifacts/stories/3-4-download-and-upload-failure-handling.md`。

### 4.4 资源保护

```
磁盘 < 2GB → 跳过本轮下载（checkpreflight_space）
内存流式处理 → iter_content(chunk_size=8192)
日志轮转 → 10MB / 5 备份
本地文件 → 7 天自动清理
```

---

## 5. 安全设计

- **日志脱敏**: `LogSanitizer` 正则过滤 Cookie、Token、OAuth 凭证
- **代理隔离**: 所有外部请求统一经由 `ConfigManager.get_proxies()`
- **热重载**: 配置文件变更无需重启，下次循环自动生效
- **凭证存储**: OAuth `token.json` 存储在项目根目录（生产环境建议加密）

---

## 6. 文件结构

```
douyin搬运/
├── main.py                  # 入口：初始化调度器 + 托盘
├── config.json              # 运行时配置（不提交 Git）
├── douyinsync.db            # SQLite 数据库（不提交 Git）
├── modules/                 # 核心业务逻辑
│   ├── scheduler.py         # PipelineCoordinator（主调度）
│   ├── database.py          # AppDatabase + VideoDAO
│   ├── config_manager.py    # ConfigManager 单例
│   ├── douyin_fetcher.py    # 抖音 API 抓取
│   ├── downloader.py        # 视频下载 + 封面生成
│   ├── youtube_uploader.py  # YouTube 上传
│   ├── notifier.py          # Bark iOS 推送
│   ├── sweeper.py           # 磁盘清理
│   ├── tray_app.py          # 托盘应用逻辑
│   ├── win_ocr.py           # Windows OCR 封装
│   └── logger.py            # 日志模块导出
├── ui/                      # GUI 组件
│   ├── dashboard_app.py     # CustomTkinter HUD 仪表盘
│   └── tray_icon.py         # PyStray 托盘图标
├── utils/                   # 通用工具
│   ├── models.py            # 数据模型 (Dataclasses)
│   ├── decorators.py        # 重试/熔断装饰器
│   ├── exceptions.py        # 自定义异常
│   ├── logger.py            # 日志配置（轮转 + 脱敏）
│   └── sanitizer.py         # 日志脱敏过滤器
├── tests/                   # 单元测试（pytest）
├── docs/                    # 项目文档（本目录）
└── downloads/               # 临时下载目录（自动清理）
```
