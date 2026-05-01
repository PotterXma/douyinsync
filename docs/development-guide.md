# 开发指南

> **最后更新**: 2026-05-01 | 面向参与 DouyinSync 开发的工程师

---

## 1. 环境搭建

### 前置要求

- **OS**: Windows 10/11（WinRT OCR 依赖）
- **Python**: 3.10+（推荐 3.11）；GitHub CI 在 Windows 上对 **3.10–3.13** 跑全量 `pytest`
- **权限**: 普通用户即可（无需管理员）

### 安装依赖

```bash
pip install -r requirements.txt
```

运行单元测试时需额外安装开发依赖（含 `pytest`、`pytest-asyncio`）：

```bash
pip install -r requirements-dev.txt
```

测试发现范围与 **asyncio** 模式由仓库根 **`pytest.ini`** 配置（`testpaths=tests`、`asyncio_mode=auto`）。

### 配置文件

在 **`data_root()`**（通常为项目根或 exe 同目录）创建 `config.json`。**完整键说明与调度示例** 以仓库根 **[README.md](../README.md)** 为准；下方为旧版结构示例，若与当前 `config.json` 不一致请以你磁盘上的文件或 README 为准：

```json
{
  "targets": [
    {
      "douyin_id": "你的抖音用户ID",
      "name": "YouTube频道标识"
    }
  ],
  "proxies": {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
  },
  "bark_server": "https://api.day.app",
  "bark_key": "你的Bark推送Key",
  "bark_sound": "minuet",
  "daily_upload_limit": 5,
  "max_videos_per_run": 3,
  "retention_days": 7,
  "scheduler_interval_minutes": 30
}
```

### YouTube OAuth 授权

首次运行会触发 OAuth 浏览器授权，生成 `token.json`。  
确保 `client_secret.json` 已放置在项目根目录。

---

## 2. 运行与调试

### 启动守护进程

```bash
python main.py
```

- 系统托盘图标出现后即代表后台服务已启动
- 右键托盘图标可打开 HUD 仪表盘或退出

### 模块化测试（不触发完整调度）

```bash
# 仅测试抖音抓取
python test_pipeline.py fetch

# 仅测试下载
python test_pipeline.py download

# 仅测试 YouTube 上传
python test_pipeline.py upload
```

### 打包为 Windows 可执行文件

```bash
build.bat
```

`build.bat` 会先 **结束 `DouyinSync.exe`**，并结束 **当前项目目录下** 命令行包含 `main.py` 的 `python.exe` / `pythonw.exe`（避免锁住 `dist` 内文件），再调用 **`DouyinSync.spec`** 输出到 `dist\_staging` 后同步到 `dist\DouyinSync\`。

打包（PyInstaller **onedir** + `COLLECT`）后，子进程 UI 通过 **同一可执行文件 + 子命令参数** 启动（与源码 `python main.py <cmd>` 对齐）：

| 子命令 | 用途 |
|--------|------|
| `dashboard` | CustomTkinter HUD 大盘 |
| `videolib` | 经典 Tk 视频库（筛选 / 重置 Pending） |
| `settings` | **搬运时间设置看板**（间隔/定点排期；保存后写 `.reload_config_request`） |
| `stats` | 统计视图 |
| `bark_test` | 可选 `[消息]`，测试 Bark 推送（不跑管道） |

示例（冻结目录下，将 `DouyinSync.exe` 换为你的实际路径）：

```text
DouyinSync.exe dashboard
DouyinSync.exe videolib
```

### BMAD 与冲刺状态

- 配置：`_bmad/bmm/config.yaml`
- 规划：`/_bmad-output/planning-artifacts/`（含 `epics/index.md` 分片索引）
- 逐故事笔记：`/_bmad-output/implementation-artifacts/stories/*.md`
- 状态文件：`_bmad-output/implementation-artifacts/sprint-status.yaml`

---

## 3. 测试规范

### 运行全量测试

```bash
python -m pytest tests/ -v
```

### 运行单个测试文件

```bash
python -m pytest tests/test_notifier.py -v
```

### 测试覆盖率检查

```bash
python -m pytest tests/ --cov=modules --cov=utils --cov-report=term-missing
```

### 测试编写规范

1. **使用 `unittest.mock.patch`** 隔离外部依赖（网络、DB、文件系统）
2. **Mock 抖音/YouTube API**，禁止测试中发起真实网络请求
3. **使用 `tmp_path` fixture** 创建临时文件，不污染项目目录
4. **模块导入延迟**：在 `patch` 上下文内执行 `from modules.xxx import Xxx`，确保 Mock 生效

---

## 4. 编码规范

### 必须遵守

| 规则 | 说明 |
|------|------|
| **使用 `logger`** | `from modules.logger import logger`，禁止 `print()` |
| **绝对导入** | `from modules.database import VideoDAO`，禁止相对导入 |
| **PyInstaller 路径** | 使用 `sys.frozen` 判断，不能写死 `__file__` |
| **懒惰日志格式** | `logger.info("msg %s", var)`，禁止 f-string 插入日志 |
| **流式 I/O** | 大文件必须 `iter_content(chunk_size=8192)`，禁止一次性 `read()` |
| **DB 连接** | 必须通过 `with db.get_connection() as conn:` |

### 禁止事项

| 禁止 | 原因 |
|------|------|
| `time.sleep()` 在 UI 线程 | 阻塞 Tkinter 主循环 |
| 硬编码凭证/Token | 安全漏洞 |
| 裸 `sqlite3.connect()` | 绕过 WAL 和超时配置 |
| `print()` 调试输出 | 无法轮转/脱敏，污染日志 |
| UI 层执行 `UPDATE/INSERT` | 破坏单向数据流原则；*例外：经典 `videolib` 仅通过 `VideoDAO.bulk_reset_to_pending` 做操作员纠偏* |
| 在托盘回调中阻塞 | PyStray 主线程死锁 |

---

## 5. 关键设计模式

### 状态机操作

```python
# ✅ 正确：通过 VideoDAO 更新状态
VideoDAO.update_status(
    record.douyin_id,
    "downloading",
    {"local_video_path": str(file_path)}
)

# ❌ 错误：绕过 DAO 直接执行 SQL
conn.execute("UPDATE videos SET status=? WHERE ...", ...)
```

### 非阻塞 UI 更新

```python
# ✅ 正确：使用 .after() 调度
self.root.after(3000, self.poll_db)

# ❌ 错误：在 UI 线程 sleep
import time; time.sleep(3)
```

### 配置读取

```python
# ✅ 正确：通过 ConfigManager
from modules.config_manager import config
proxies = config.get_proxies()

# ❌ 错误：直接读取 JSON 文件
import json; data = json.load(open("config.json"))
```

---

## 6. 常见问题

### Q: 抖音抓取返回空列表？
- 检查 `config.json` 中的 `douyin_id` 是否正确
- 检查代理是否可用（`proxies` 配置）
- 抖音 Cookie 可能已过期，需要更新

### Q: YouTube 上传报 403？
- 配额超限（每日 10,000 点，每视频约 1,600 点）
- 系统自动触发熔断器，等待至 PST 次日零时恢复

### Q: 数据库锁超时？
- WAL 模式 + `busy_timeout=10000ms` 已覆盖大多数场景
- 检查是否有外部工具正在持有写锁

### Q: HUD 仪表盘数据不更新？
- Dashboard 每 3 秒轮询一次
- 检查 `modules/database.py` 中 `get_pipeline_stats()` 是否正常工作
