# DouyinSync 项目文档索引

> **最后更新**: 2026-04-24 | **版本**: v1.1.1（下载/上传失败策略 §4.3；BMAD Story 3.4 / 4.4）

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
| 测试入口 | `python -m pytest tests/` |
| 打包脚本 | `build.bat`（PyInstaller） |

## 文档目录

### 核心文档

| 文档 | 说明 |
|------|------|
| [项目概览](./project-overview.md) | 功能说明、Epic 交付列表、快速启动 |
| [架构设计](./architecture.md) | 系统架构、组件关系、数据流；**§4.3** 下载/上传失败与重试 |
| [数据模型](./data-models.md) | VideoRecord、AppConfig 等数据结构 |
| [API 契约](./api-contracts.md) | 各模块公共接口签名与行为规范 |
| [组件清单](./component-inventory.md) | 全部模块职责速览 |
| [开发指南](./development-guide.md) | 环境搭建、编码规范、测试方法 |
| [项目上下文](./project-context.md) | AI 代理守则、实现约束、禁止事项 |

### Cursor / AI 协作

| 项目 | 说明 |
|------|------|
| [AGENTS.md](../AGENTS.md) | Cursor Agent 入口说明（文档与技能路径） |
| `.cursor/rules/` | 始终生效的项目级规则 |
| `.cursor/skills/` | BMAD 等方法论技能（项目内唯一技能副本） |
| [documents/](../documents/README.md) | 规范中的 `documents/` 入口（正文在 `docs/`） |
| [_bmad-output/](../_bmad-output/README.md) | BMAD 产出总索引 |

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
