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

## Repository Structure
This is a Monolith architecture. All modules live within `/modules/` and decouple into distinct responsibilities unified by `scheduler.py` via APScheduler loops. Local persistent data gets saved safely under `/dist/` and media caching inside `/downloads/`.
