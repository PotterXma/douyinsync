## ✅ 已关闭 — 来自：code review of 3-3-customtkinter-hud-dashboard.md (2026-04-22)

- ~~Synchronous 'poll_db' could block mainloop [ui/dashboard_app.py:71]~~
  - **已由 Story 3.4 解决**：改用 `root.after(3000, self.poll_db)` 非阻塞轮询 + `finally` 块重新注册，完全符合 Tkinter 主线程规范。(验证日期: 2026-04-22)

## ✅ 已关闭 — 来自：code review of story-3.2 (2026-04-22)

- ~~Midnight rollover race condition: `push_daily_summary()` resets the counter if delayed past midnight, causing zero-counts.~~
  - **已修复**：新增 `_snapshot_and_reset_daily_counter()` 方法，先快照计数再执行日期重置，保证跨午夜延迟触发时前一天数据不丢失。新增 3 个竞态回归测试，12/12 全通过。(修复日期: 2026-04-22)
