# API 契约文档

> **最后更新**: 2026-04-22 | **覆盖模块**: VideoDAO、ConfigManager、BarkNotifier、DiskSweeper

---

## VideoDAO — 数据访问对象

**位置**: `modules/database.py`  
**实例**: 通过模块级 `db = AppDatabase(DB_FILE)` 单例实现，所有方法为静态方法。

---

### `insert_video_if_unique`

```python
@staticmethod
def insert_video_if_unique(record: VideoRecord) -> bool
```

**职责**: 幂等插入。若 `douyin_id` 已存在则忽略。  
**返回**: `True` = 新行已插入；`False` = 已存在被忽略。  
**副作用**: 自动填充 `created_at` / `updated_at` 为当前 Unix 时间戳。

---

### `update_status`

```python
@staticmethod
def update_status(douyin_id: str, new_status: str, extra_updates: dict = None) -> None
```

**参数**:
- `douyin_id`: 目标视频 ID
- `new_status`: 新状态字符串（见状态机）
- `extra_updates`: 可选附加列更新（如 `{"local_video_path": "/path/to/file.mp4"}`）

**副作用**: 自动更新 `updated_at`。

---

### `get_pending_videos`

```python
@staticmethod
def get_pending_videos(limit: int = 5) -> list[VideoRecord]
```

**职责**: 按 `created_at` 升序返回最早的 `limit` 条 `pending` 视频。

---

### `get_uploadable_videos`

```python
@staticmethod
def get_uploadable_videos(limit: int = 1, *, ignore_retry_cap: bool = False) -> list[VideoRecord]
```

**职责**: 返回可上传视频（`status='downloaded'` 或 `status='failed'` 且本地文件存在）。  
**限流**: 默认对整段 WHERE 附加 `retry_count < 3`（含纯 `downloaded` 行）。`ignore_retry_cap=True` 时去掉该条件（供 Dashboard **手动重新执行** 触发的 `force_retry_bypass` 周期使用）。

---

### `prepare_for_force_manual_retry`

```python
@staticmethod
def prepare_for_force_manual_retry() -> int
```

**职责**: 将 `give_up` / `give_up_fatal` / `failed` 等行归一化为可再次下载或上传的状态，并返回受影响行数之和。  
**调用方**: `PipelineCoordinator._run_async_cycle(force_retry_bypass=True)` 开头。  
**事务**: 使用 `BEGIN IMMEDIATE` 包裹四条 `UPDATE`，全成功提交或失败回滚，避免部分归一化。

---

### `get_uploaded_today_count`

```python
@staticmethod
def get_uploaded_today_count() -> int
```

**职责**: 统计今日（本地时区）成功上传的视频数量。  
**用途**: 对比 `config.json` 中的 `daily_upload_limit` 实现配额控制。

---

### `revert_zombies`

```python
@staticmethod
def revert_zombies() -> int
```

**职责**: 崩溃自愈机制。将遗留在 `processing`/`downloading` 状态的记录重置为 `pending`，将 `uploading` 重置为 `downloaded`。  
**调用时机**: 每次 `main.py` 启动时调用一次。  
**返回**: 被重置的行数。

---

### `update_fresh_urls`

```python
@staticmethod
def update_fresh_urls(douyin_id: str, video_url: str, cover_url: str) -> None
```

**职责**: 更新过期的 CDN 链接为最新鲜的 URL（应对抖音 CDN 令牌过期导致 403）。

---

### `get_pipeline_stats`

```python
@staticmethod
def get_pipeline_stats() -> dict[str, int]
```

**职责**: 按 status 聚合统计所有视频数量。  
**返回示例**:
```python
{"pending": 12, "uploaded": 180, "failed": 3, "give_up_fatal": 1}
```
**用途**: Dashboard UI 每 3 秒轮询一次用于实时展示。

---

### `get_accounts_pipeline_stats`

```python
@staticmethod
def get_accounts_pipeline_stats() -> dict[str, dict[str, int]]
```

**职责**: 按 `account_mark` 分组，再按 `status` 聚合计数；空账号归并为 `"Unknown"`。  
**用途**: Epic 5 CustomTkinter 大盘「分账号进度」卡片。

---

### `get_recent_failure_rows`

```python
@staticmethod
def get_recent_failure_rows(limit: int = 25) -> list[dict[str, object]]
```

**职责**: 返回最近更新的失败类记录（`failed` / `give_up` / `give_up_fatal`），字段含 `douyin_id`、`title`、`account_mark`、`status`、`retry_count`、`local_video_path`、`updated_at`。  
**用途**: Dashboard 只读「最近失败」面板。

---

### `list_videos_for_library`

```python
@staticmethod
def list_videos_for_library(filter_status: Optional[str] = None, limit: int = 500) -> list[tuple]
```

**职责**: 为经典视频库表格返回行元组  
`(douyin_id, status, account_mark, retry_count, title, local_video_path)`。  
`filter_status` 为 SQLite 中精确的 `status` 值，或 `None` 表示不按状态过滤。

---

### `bulk_reset_to_pending`

```python
@staticmethod
def bulk_reset_to_pending(douyin_ids: list[str]) -> int
```

**职责**: 将给定 `douyin_id` 批量置为 `pending` 且 `retry_count=0`；返回受影响行数。  
**用途**: `modules/dashboard.py`（`videolib`）重置选中任务。

---

## ConfigManager — 配置管理器

**位置**: `modules/config_manager.py`  
**模式**: 线程安全单例（`threading.Lock`）  
**实例**: `from modules.config_manager import config`（已导出）

---

### `load_config`

```python
def load_config(self) -> AppConfig
```

**职责**: 从 `config.json` 读取并解析为强类型 `AppConfig`。  
**异常**:
- `ConfigNotFoundError` — 文件不存在，**阻断启动**
- `ConfigParseError` — JSON 格式错误或缺少 `targets` 字段，**阻断启动**

---

### `get`（兼容层）

```python
def get(self, key: str, default=None) -> Any
```

**注意**: 遗留兼容接口，新代码应直接访问 `config.config` 获取强类型对象。  
**支持键**: `"proxies"`（返回 `dict`），其他键返回 `default`。

---

### `get_proxies`

```python
def get_proxies(self) -> dict | None
```

**返回**: `requests` 兼容的代理字典，如 `{"http": "http://127.0.0.1:7890", "https": ...}`，若无代理配置则返回 `None`。

---

## BarkNotifier — 推送通知器

**位置**: `modules/notifier.py`  
**实例化**: 每次使用需独立实例化（内含每日计数状态）。

---

### `push`

```python
def push(self, title: str, message: str, level: str = "active") -> None
```

**`level` 取值**:

| 值 | 行为 |
|----|------|
| `"active"` | 默认响铃通知 |
| `"timeSensitive"` | 关键通知（可穿透专注模式） |
| `"passive"` | 静默收件箱（不响铃） |

**容错**: 网络失败时仅 `logger.warning`，不抛出异常。  
**热重载**: 每次调用动态读取 `config.json` 中的 `bark_server`/`bark_key`。

---

### `record_upload_success`

```python
def record_upload_success(self) -> None
```

**职责**: 每次成功上传后调用，递增每日计数器。  
**线程安全**: 单线程场景设计，调用方需确保串行调用。

---

### `push_daily_summary`

```python
def push_daily_summary(self) -> None
```

**职责**: 发送当日上传汇总（`level="passive"`）。  
**跨午夜安全**: 使用快照-重置模式（`_snapshot_and_reset_daily_counter`），即使调度器延迟至次日也保证计数准确。  
**空值保护**: 计数为 0 时静默跳过。

---

## DiskSweeper — 磁盘清理器

**位置**: `modules/sweeper.py`

---

### `check_preflight_space`

```python
def check_preflight_space(self) -> bool
```

**职责**: 检测 `downloads/` 所在分区是否有 ≥ 2GB 可用空间。  
**返回**: `False` = 空间不足，调度器应跳过本轮下载。  
**容错**: IO 异常时返回 `True`（保守放行）。

---

### `purge_stale_media`

```python
def purge_stale_media(self, max_age_days: int = 7) -> None
```

**职责**: 递归扫描 `downloads/` 目录，删除超过 `max_age_days` 天的 `.mp4`、`.webp`、`.jpg` 文件。  
**容错**: 单文件删除失败（权限、占用）仅 warning 跳过，不中断整体清扫。  
**推荐调用**: 每次调度循环开始前调用一次。

---

## 装饰器 API

**位置**: `utils/decorators.py`

### `@auto_retry`

```python
@auto_retry(max_retries=3, backoff_base=2.0, exceptions=(BasePipelineError,))
```

**行为**: 指数退避重试（1s → 2s → 4s）。同时支持 `async` 和 `sync` 函数。  
**超出重试次数**: 重新抛出最后一次异常。

### `@circuit_breaker`

```python
@circuit_breaker(trip_on=(YoutubeQuotaError,))
```

**行为**: 触发指定异常后立即挂起（休眠至 PST 次日零时），用于 YouTube 配额超限场景。  
**注意**: 触发后异常仍会向上传播，调用方需额外捕获。
