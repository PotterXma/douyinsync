# 数据模型文档

> **最后更新**: 2026-04-22 | **来源**: `utils/models.py`、`modules/database.py`

---

## 核心数据模型

### `VideoRecord` — 视频状态记录

```python
@dataclass
class VideoRecord:
    douyin_id: str              # 抖音视频唯一 ID（主键）
    account_mark: str = ""      # 来源账号标识（对应 config.json 中的 name）
    title: str = ""             # 视频标题
    description: str = ""      # 视频描述/文案
    video_url: str = ""         # 抖音 CDN 视频直链（有过期时间）
    cover_url: str = ""         # 抖音封面图 WebP 链接（有过期时间）
    status: str = "pending"     # 当前处理状态（见状态机）
    retry_count: int = 0        # 已重试次数（≥3 触发 give_up_fatal）
    local_video_path: Optional[str] = None  # 本地下载路径
    local_cover_path: Optional[str] = None  # 本地封面路径（JPEG）
    created_at: Optional[int] = None        # Unix 时间戳（首次发现）
    updated_at: Optional[int] = None        # Unix 时间戳（最后更新）
```

#### 状态机转换图

```
pending
  │
  ▼  PipelineCoordinator 锁定
processing / downloading
  │
  ▼  下载完成
downloaded
  │
  ▼  YouTube 上传开始
uploading
  │
  ▼  上传成功
uploaded ──── 终态，永不再处理

failed ◄──── 任意阶段失败（retry_count < 3 则重试）
  │
  ▼  retry_count ≥ 3
give_up_fatal ──── 终态，需人工介入
```

| 状态 | 说明 | 可逆？ |
|------|------|--------|
| `pending` | 新发现，等待处理 | 是（zombies 恢复） |
| `processing` / `downloading` | 调度器锁定中 | 是（崩溃恢复） |
| `downloaded` | 本地文件就绪 | 是（zombies 恢复） |
| `uploading` | 正在上传 YouTube | 是（崩溃恢复） |
| `uploaded` | **终态**，上传完毕 | **否** |
| `failed` | 失败，等待重试 | 是（重试） |
| `give_up_fatal` | **终态**，放弃 | **否** |

---

### `AppConfig` — 应用配置

```python
@dataclass
class AppConfig:
    targets: List[TargetConfig]   # 监控的抖音账号列表
    proxies: ProxyConfig          # 网络代理设置
```

### `TargetConfig` — 目标账号

```python
@dataclass
class TargetConfig:
    douyin_id: str         # 抖音用户 ID（必填）
    name: Optional[str]    # 账号别名/标识（对应 YouTube 频道）
```

### `ProxyConfig` — 代理配置

```python
@dataclass
class ProxyConfig:
    http: Optional[str]    # HTTP 代理地址（如 "http://127.0.0.1:7890"）
    https: Optional[str]   # HTTPS 代理地址
```

### `AppEvent` — 组件间事件

```python
@dataclass
class AppEvent:
    command: str           # 事件指令（如 "show_dashboard"、"reload_config"）
    payload: Optional[Any] = None  # 附加数据（可选）
```

---

## 异常体系

```python
# utils/models.py
YoutubeUploadError      # YouTube 上传基类异常
  ├── YoutubeQuotaError    # 配额超限（触发熔断，等待至次日 PST 午夜）
  └── YoutubeNetworkError  # 网络故障（触发 auto_retry 重试）

# modules/database.py
DatabaseConnectionError  # SQLite 连接或初始化失败（阻断启动）

# modules/config_manager.py
ConfigNotFoundError      # config.json 文件不存在（阻断启动）
ConfigParseError         # JSON 格式错误或缺少必填字段（阻断启动）
```

---

## SQLite 表结构

### `videos` 表

```sql
CREATE TABLE IF NOT EXISTS videos (
    douyin_id        TEXT PRIMARY KEY,  -- 抖音视频 ID
    account_mark     TEXT,               -- 账号标识
    title            TEXT,               -- 标题
    description      TEXT,               -- 描述
    video_url        TEXT,               -- CDN 视频链接（可能过期）
    cover_url        TEXT,               -- CDN 封面链接（可能过期）
    status           TEXT DEFAULT 'pending',
    retry_count      INTEGER DEFAULT 0,
    local_video_path TEXT,               -- 本地视频文件路径
    local_cover_path TEXT,               -- 本地封面文件路径（JPEG）
    created_at       INTEGER,            -- Unix 时间戳
    updated_at       INTEGER             -- Unix 时间戳
);

PRAGMA journal_mode = WAL;     -- 写前日志，支持读写并发
PRAGMA synchronous = NORMAL;   -- 性能与安全平衡
PRAGMA busy_timeout = 10000;   -- 10 秒等待锁超时
```
