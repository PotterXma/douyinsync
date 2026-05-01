# DouyinSync 项目文档索引

> **最后更新**: 2026-05-01 | **版本**: v1.2.2（`requirements-dev.txt`、GitHub Actions CI、videolib 导出与 limits）

## 项目概述

- **类型**: Python 单体后台守护进程
- **主要语言**: Python 3.10+
- **架构**: 事件驱动定时调度管道（APScheduler + SQLite 状态机）
- **运行平台**: Windows 10/11（支持 PyInstaller 打包为 `.exe`）

## 快速参考

| 项目 | 值 |
|------|----|
| 入口点 | `main.py` |
| 数据库 | `douyinsync.db`（SQLite WAL 模式） |
| 配置文件 | `config.json` |
| 测试入口 | `pip install -r requirements-dev.txt` 后 `python -m pytest tests/`（`pytest.ini`） |
| CI | `.github/workflows/ci.yml`（Windows；Python **3.10–3.13** 矩阵 + `pytest`；任意 PR；可 **Run workflow**） |
| 打包脚本 | `build.bat` 或 `scripts/build_douyinsync.ps1`（PyInstaller） |

## 文档目录

### 核心文档

| 文档 | 说明 |
|------|------|
| [项目概览](./project-overview.md) | 功能说明、Epic 交付列表、快速启动 |
| [架构设计](./architecture.md) | 系统架构、组件关系、数据流；**§4.3** 下载/上传失败与重试 |
| [数据模型](./data-models.md) | VideoRecord、AppConfig 等数据结构 |
| [API 契约](./api-contracts.md) | 各模块公共接口；含 **`utils.paths`**（`data_root`、哨兵文件） |
| [组件清单](./component-inventory.md) | 全部模块职责速览 |
| [开发指南](./development-guide.md) | 环境搭建、编码规范、测试方法 |
| [源码树分析](./source-tree-analysis.md) | 目录职责、入口点、忽略路径（BMAD Source Tree） |
| [部署与分发](./deployment-guide.md) | PyInstaller、`data_root`、侧车文件、哨兵文件 |
| [BMAD 文档流程对齐](./bmad-documentation-alignment.md) | BMM 路径、`document-project` 技能与 `docs/` 分工 |
| [项目上下文](./project-context.md) | AI 代理守则、实现约束、禁止事项 |

### Cursor / AI 协作

| 项目 | 说明 |
|------|------|
| [AGENTS.md](../AGENTS.md) | Cursor Agent 入口说明（文档与技能路径） |
| `.cursor/rules/` | 始终生效的项目级规则 |
| `.cursor/skills/` | BMAD 等方法论技能（项目内唯一技能副本） |
| [documents/](../documents/README.md) | 规范中的 `documents/` 入口（正文在 `docs/`） |
| [_bmad-output/](../_bmad-output/README.md) | BMAD 产出总索引 |
| [文档扫描基线](../_bmad-output/documentation/project-scan-report.json) | 本次文档补全的轻量状态记录（可删，仅追溯用） |

### 参考资料

- [README.md](../README.md) — 面向用户的主文档
- [BMAD 规划索引](../_bmad-output/planning-artifacts/README.md) — PRD 快照、产品简报、Epic 分片、回顾、追溯矩阵、实现就绪
- [Epic 分片索引](../_bmad-output/planning-artifacts/epics/index.md) — `epic-1..5` 导航
- [逐故事笔记](../_bmad-output/implementation-artifacts/stories/) — 与 `sprint-status.yaml` 键对齐的 **17** 个 `*.md`（含 [3-4 下载/上传失败](../_bmad-output/implementation-artifacts/stories/3-4-download-and-upload-failure-handling.md)、[4-4 手动运行与排期](../_bmad-output/implementation-artifacts/stories/4-4-manual-run-and-schedule-modes.md)）
- [BMAD 冲刺状态](../_bmad-output/implementation-artifacts/sprint-status.yaml) — `development_status` 与 `epic-*-retrospective` 均为 done
- [测试摘要](../tests/test-summary.md) — 测试覆盖说明

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 config.json（参照 README）

# 3. 启动守护进程
python main.py

# 4. 运行全量测试
python -m pytest tests/ -v
```
