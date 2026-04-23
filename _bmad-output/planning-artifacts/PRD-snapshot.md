# DouyinSync — PRD 快照（BMAD 规划补档）

> **版本**: 1.1 | **状态**: 与当前代码库对齐 | **语言**: zh-CN

## 1. 产品愿景

在 **Windows** 上长期无人值守运行，自动监视指定抖音创作者，将视频与封面搬运至 **YouTube**，并在异常时通过 **Bark** 与本地 **仪表盘** 可观测。

## 2. 目标用户与场景

| 角色 | 场景 |
|------|------|
| 运营者 / 自媒体 | 单机或小型服务器 7×24 同步，少人工干预 |
| 技术维护者 | 通过托盘与独立子进程 UI 查看状态、调整间隔、手动重试 |

## 3. 功能需求（FR）

| ID | 描述 |
|----|------|
| FR-01 | 支持多 `douyin_accounts`（sec_uid）轮询抓取新作品列表 |
| FR-02 | 以 `douyin_id` 幂等入库，避免重复搬运 |
| FR-03 | 流式下载大文件，控制内存；WebP/封面处理与 OCR 叠加（Windows） |
| FR-04 | 抖音与 YouTube 可使用不同代理策略 |
| FR-05 | YouTube OAuth + 可续传分块上传 + 自定义缩略图 |
| FR-06 | APScheduler 定时触发整管道；可托盘暂停/恢复 |
| FR-07 | 崩溃后僵尸状态恢复（processing/downloading/uploading） |
| FR-08 | YouTube 配额熔断，次日自动恢复尝试 |
| FR-09 | 磁盘空间预检与过期媒体清理（Sweeper） |
| FR-10 | Bark 推送关键异常与日报类信息 |
| FR-11 | **子进程** 打开仪表盘：`dashboard`（CTk HUD）、`videolib`（经典表）、`settings` / `stats` |
| FR-12 | HUD 只读 DB；经典库允许操作员将选中项重置为 `pending`（与架构「HUD 只读」区分：管理库可写） |

## 4. 非功能需求（NFR）

| ID | 描述 |
|----|------|
| NFR-01 | 主进程托盘线程不因管道阻塞而僵死 |
| NFR-02 | SQLite WAL + busy_timeout，支持 UI 轮询与管道并发写 |
| NFR-03 | 日志轮转 + 脱敏（Cookie/Token） |
| NFR-04 | 支持 PyInstaller 冻结路径（`sys.frozen`） |
| NFR-05 | 核心模块具备自动化单元测试（pytest） |

## 5. 明确不包含（本期）

- Linux / macOS 正式支持
- 多频道 OAuth 以外的多租户 SaaS
- 抖音/YouTube 之外的第三方发布渠道（可扩展但非本期 PRD）

## 6. 验收总原则

- 每条 Story 的 **Given/When/Then** 在 `epics-and-stories.md` 中列出；实现对应见 `traceability-matrix.md`。
- 回归：`python -m pytest tests/ -q` 全绿。
