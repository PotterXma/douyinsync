# Project Overview: DouyinSync

## Executive Summary
DouyinSync provides a robust, zero-touch operational automation pipeline for monitoring target Douyin (TikTok China) creators and migrating their content to YouTube autonomously. Featuring memory-friendly chunk downloading, an embedded SQLite state engine, WAF circumventions via specific signatures, and a Tkinter system-tray interface.

## Tech Stack
| Category | Technology | Version | Purpose |
|----------|------------|---------|---------|
| Core | Python | 3.9+ | Main runtime language |
| Database | SQLite3 | - | Native file system ACID database for video tracking |
| Scheduling | APScheduler | Latest | Headless background chron task management |
| GUI | Tkinter & PyStray | - | Background task tray operations window and dashboards |
| Client | Google Python API | V3 | Interacting with YouTube services |
| Testing | Unittest | Core | E2E and module pipeline verification |

## 交付状态（与代码对齐）

| 范围 | 状态 |
|------|------|
| 管道 / 抓取 / 下载 / 上传 / 清理 / 通知 | 已实现；见 `docs/architecture.md` |
| Epic 5 可视化 | **已交付**：`main.py dashboard`（CustomTkinter HUD）、`main.py videolib`（经典管理库） |

> BMAD：规划产物位于 `_bmad-output/planning-artifacts/` 与 `_bmad-output/implementation-artifacts/`；配置见 `_bmad/bmm/config.yaml`。验收以该目录 + `docs/` + `pytest` 为准。

## Repository Structure
This is a Monolith architecture. Core logic lives in `/modules/` and is driven by `scheduler.py` (APScheduler). GUI entry points live under `/ui/`. Local persistent data and media cache follow paths described in `README.md` / `docs/architecture.md` (e.g. project root DB file `douyinsync.db`, `downloads/`).
