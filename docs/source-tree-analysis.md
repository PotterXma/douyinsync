# 源码树分析（Source Tree）

> **最后更新**: 2026-05-01 | 与 BMAD `document-project` 清单「Source Tree Analysis」对齐

本文描述仓库 **目录职责**、**入口点** 与 **应忽略路径**，便于 AI 与人类快速定位代码。

---

## 1. 顶层结构

| 路径 | 说明 |
|------|------|
| `main.py` | 进程入口：日志初始化 → 守护线程（`PipelineCoordinator`）→ 托盘主循环（`TrayApp`）；支持子命令 `dashboard` / `videolib` / `settings` / `stats` / `bark_test` 等 |
| `DouyinSync.spec` | PyInstaller 规格（onedir + `COLLECT`） |
| `config.example.json` | `config.json` 无密钥模板（可复制后本地填写）；真实配置勿入库 |
| `build.bat` | Windows 打包：结束占用进程 → 清理 `build` / `dist\_staging` → `pyinstaller` → 同步到 `dist\DouyinSync\` |
| `requirements.txt` | 运行时依赖（托盘、管道、UI） |
| `requirements-dev.txt` | 在上一文件基础上：`pytest`、`pytest-asyncio`（与 CI 一致） |
| `.github/workflows/ci.yml` | Windows；Python 3.10–3.13 矩阵；全量 `pytest`；任意 PR |
| `.github/dependabot.yml` | Actions / pip 依赖扫描（按月 PR） |
| `pytest.ini` | `pytest` 入口：`testpaths`、`asyncio_mode=auto` |
| `config.json`（示例/本地） | 开发时置于 `data_root()`；与 `client_secret.json`、`youtube_token.json` 等为敏感侧车文件 |

---

## 2. 应用代码（应优先阅读）

| 路径 | 说明 |
|------|------|
| `modules/` | 核心业务：**`scheduler.py`**（管道 + APScheduler）、`database.py`、`douyin_fetcher.py`、`downloader.py`、`youtube_uploader.py`、`config_manager.py`、`notifier.py`、`sweeper.py`；**`ui_settings.py`**（搬运时间设置看板）、`dashboard.py`（经典库入口）等 |
| `ui/` | **`tray_icon.py`**（当前主程序使用的托盘菜单）、`dashboard_app.py`（CustomTkinter HUD 子进程） |
| `utils/` | **`paths.py`**（`data_root()`、`DOUYINSYNC_DATA_DIR`、哨兵文件路径）、`models.py`、`logger.py` 等 |

---

## 3. 数据与产物（运行时生成）

| 路径 | 说明 |
|------|------|
| `downloads/` | 视频/封面缓存（相对 `data_root()`） |
| `logs/` | 应用日志目录（`data_root()/logs`） |
| `douyinsync.db` | SQLite 状态库（路径随 `data_root()`） |
| `.manual_sync_request` / `.manual_force_retry_request` | HUD 或外部触发的单次同步请求文件 |
| `.reload_config_request` | 设置看板保存后通知主进程 `reload` + 重挂主同步任务 |
| `.hud_scheduler_state.json` | 主进程写入的调度快照，供 HUD 只读展示 |

> 冻结 exe 场景下，以上路径默认相对于 **`DouyinSync.exe` 所在目录**，除非设置环境变量 **`DOUYINSYNC_DATA_DIR`**。

---

## 4. 文档与 BMAD 产出

| 路径 | 说明 |
|------|------|
| `docs/` | **工程权威说明**：索引 `index.md`、架构、数据模型、API 契约、开发指南等 |
| `documents/` | 规范要求的 `documents/` **入口**；正文链接回 `docs/`（见 `documents/README.md`） |
| `_bmad/bmm/config.yaml` | BMM 路径变量：`planning_artifacts`、`implementation_artifacts`、`project_knowledge` 等 |
| `_bmad-output/planning-artifacts/` | PRD 快照、Epic 分片、追溯矩阵、实现就绪报告等 |
| `_bmad-output/implementation-artifacts/` | `sprint-status.yaml`、装配说明、`stories/*.md` 逐故事笔记 |

---

## 5. 测试与构建产物（扫描时降级）

| 路径 | 说明 |
|------|------|
| `tests/` | `pytest` 用例；与 `modules/`、`utils/` 镜像覆盖 |
| `build/`、`dist/` | PyInstaller 中间产物与分发目录；**勿手改** `dist\_staging`（每次构建重建） |
| `.cursor/` | Cursor 规则与 BMAD 技能副本；不参与运行时 |

---

## 6. 入口点速查

| 场景 | 入口 |
|------|------|
| 正常守护 + 托盘 | `python main.py` |
| HUD 子进程 | `python main.py dashboard` 或 `DouyinSync.exe dashboard` |
| 视频管理库 | `python main.py videolib` |
| 搬运时间设置看板 | `python main.py settings` |
| 统计窗口 | `python main.py stats` |
| Bark 测试推送 | `python main.py bark_test [可选消息]` |

---

## 7. 与架构文档的关系

数据流、组件边界、失败重试策略等 **语义设计** 见 [architecture.md](./architecture.md)；本文仅提供 **物理树导航**，二者互补。
