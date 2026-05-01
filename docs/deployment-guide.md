# 部署与分发指南（Deployment）

> **最后更新**: 2026-05-01 | 与 BMAD `document-project` 清单「Deployment」对齐（Windows / PyInstaller；含 `config.example.json`）

---

## 1. 分发形态

| 形态 | 说明 |
|------|------|
| **源码** | `pip install -r requirements.txt` 后 `python main.py` |
| **PyInstaller onedir** | `build.bat` 或 `scripts\build_douyinsync.ps1` 生成 `dist\DouyinSync\`，内含 `DouyinSync.exe` 与同目录依赖 DLL / 包 |

---

## 2. 构建步骤

1. **关闭**正在运行的 `DouyinSync.exe`（否则可能 `PermissionError`）。
2. 关闭在本仓库以 `main.py` 启动的 `python.exe` / `pythonw.exe`（`build.bat` 会尝试结束相关进程）。
3. 仓库根目录执行：

```bat
build.bat
```

无交互 CI 可加参数：`build.bat nopause`。

PowerShell（与 `build.bat` 等价；自动化加 `-NoPause`）：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_douyinsync.ps1
pwsh -File .\scripts\build_douyinsync.ps1 -NoPause
```

4. 成功标志：控制台出现 `[SUCCESS]`；可执行文件路径：`dist\DouyinSync\DouyinSync.exe`。

---

## 3. 数据根目录（`data_root()`）

运行时 **`config.json`**、**`douyinsync.db`**、**`logs/`**、**`downloads/`** 等均解析自 `utils.paths.data_root()`：

| 场景 | 解析规则 |
|------|----------|
| **冻结 exe** | 默认可执行文件所在目录（与当前工作目录无关） |
| **源码** | 默认识别为仓库根（`utils` 的上一级） |
| **覆盖** | 环境变量 **`DOUYINSYNC_DATA_DIR`** 设为已存在的**绝对路径**目录时优先生效 |

部署到固定盘符服务时，建议将配置与库文件集中在一目录，并通过 `DOUYINSYNC_DATA_DIR` 指向该目录，避免与 exe 分离后找不到配置。

---

## 4. 侧车文件清单（首次安装 / 升级保留）

在 **`data_root()`** 下建议保留或手工放置：

| 文件 | 说明 |
|------|------|
| `config.json` | 业务配置（勿提交仓库）。仓库提供 **`config.example.json`** 无密钥模板；打包时若根目录无 `config.json` 则复制模板到 `dist\DouyinSync\config.json` |
| `client_secret.json` | Google OAuth 客户端密钥 |
| `youtube_token.json` | 授权后生成；勿提交版本库 |
| `douyinsync.db` | 状态库；升级 exe 时通常应 **保留**。仓库默认 **`.gitignore`** 忽略该文件及 WAL 附属文件（`-journal` / `-wal` / `-shm`）（勿把生产库提交进版本库） |

日志目录：`data_root()/logs/`（启动时由 `setup_logging` 创建）。

---

## 5. 子进程与哨兵文件

主进程托盘 + 后台管道；以下 UI 为 **同 exe / 同 python + 子命令** 的独立进程：

- `dashboard`、`videolib`、`settings`、`stats`

以下 **零参数文件** 由子进程或设置 UI 创建，主循环轮询消费：

| 文件 | 作用 |
|------|------|
| `.manual_sync_request` | 请求跑一轮主同步 |
| `.manual_force_retry_request` | 一轮带强制重试归一化的同步 |
| `.reload_config_request` | `config.reload()` + `apply_primary_schedule()` |

详见 [architecture.md](./architecture.md) 与 [api-contracts.md](./api-contracts.md) 中的路径工具说明。

---

## 6. 运维检查清单

- [ ] `DOUYINSYNC_DATA_DIR`（若使用）对运行账户可读写  
- [ ] 磁盘空间满足 `storage_retention_days` 与最大视频体积  
- [ ] 代理、`douyin_cookie`、YouTube 配额与 OAuth 未过期  
- [ ] 升级 exe 前备份 `config.json`、token、数据库  

---

## 7. 相关文档

- [development-guide.md](./development-guide.md) — 本地运行、测试、子命令表  
- [project-overview.md](./project-overview.md) — 能力范围与交付状态  
- [bmad-documentation-alignment.md](./bmad-documentation-alignment.md) — BMAD 文档流程与本仓库映射  
