# Story 3.3: CustomTkinter HUD Dashboard

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

作为一名操作监控员，
我想要一个美观的、暗黑模式的 CustomTkinter 仪表板来展示可视化的流水线，
以便于我可以立刻感知宏观级别的健康状况，而无需去翻阅日志。

## Acceptance Criteria

1. **Given** 用户点击“打开面板”或从系统托盘唤起 Dashboard，
   **When** GUI 初始化时，
   **Then** 它必须使用极简且严格的 CustomTkinter 模式构建，维持整个程序空闲内存占用 < 100MB。
2. **Given** 窗口弹出并在前台，
   **When** 用户点击桌面其他地方或者使得窗口失去焦点 (FocusOut) 时，
   **Then** 面板必须自动隐藏退回到系统托盘，而不是驻留在任务栏上。
3. **Given** UI 进入渲染生命周期，
   **When** 呈现数据与节点时，
   **Then** 它必须能清晰展示出顶部的 Global HUD（包含全局处理数字与 Quota 进度条），并在下方渲染出含有各频道同步状态卡片的纵向列表。

## Tasks / Subtasks

- [x] 任务 1: 创建 CustomTkinter 基础窗口并集成失去焦点隐藏机制 (AC: 1, 2)
  - [x] 在 `ui/dashboard_app.py` 中初始化基础窗口配置，启用高分屏 (DPI) 感知保护。
  - [x] 绑定 `FocusOut` 窗口失去焦点事件，确保执行窗口隐藏 (withdraw / hide) 而不是销毁程序。
- [x] 任务 2: 实现顶部的 Global HUD 面板组件 (AC: 3)
  - [x] 划分布局，在上部植入大字号展示聚合数值（例如总处理与上传量），并附带一根粗壮的 `CTkProgressBar` 作为总限额指示仪。
  - [x] 设置纯正的极黑（Dark Mode）与饱和的红/绿信号色作为色彩标记系统标尺。
- [x] 任务 3: 构建可滚动的单独源道卡片列表 (AC: 3)
  - [x] 建立以单账号视角为原型的 Widget（可命名为 `PipelineStatusCard`），内含名字、标签与一个操作按钮占位符。
  - [x] 将这些子组件统一放置在 `CTkScrollableFrame` 中形成瀑布流，用 Dummy（假数据）验证 UI 的响应式结构和性能。

### Review Findings

- [x] [Review][Patch] Missing Account Cards DB Population [ui/dashboard_app.py:71]
- [x] [Review][Patch] Unhandled Close Window Event (X button kills MainLoop) [ui/dashboard_app.py:51]
- [x] [Review][Patch] Hardcoded Magic Quota Numbers [ui/dashboard_app.py:82]
- [x] [Review][Defer] Synchronous 'poll_db' could block mainloop [ui/dashboard_app.py:71] — deferred, pre-existing (Story 3.4 will address async read flow)



## Dev Notes

### Dev Agent Guardrails

- **架构约束：**
  这只是一层负责显示结果的纯 View。绝不可以在里面插入 `urllib/httpx/sqlite3.cursor.execute("UPDATE...")` 相关的重型业务状态修改。
- **技术框架：**
  严格限制使用 `customtkinter` (禁止原生 `tkinter` 的低清样式，禁止重资源跨平台的 `Electron/CEF`)。确保打包后为极小占用体积。
- **并发与调用：**
  如果在测试本 Story 的 UI 时有阻塞或无响应现象：查验是否有耗时的同步查询。虽然这将在 Story 3-4 中最终解决只读查库问题，但此时设计 UI 需提供如 `update_data_layer(data: dict)` 这样快速的设值通道而不是在 UI 构造时读库。
- **关于失焦与呼出**
  - 使用 `self.bind("<FocusOut>", self._on_focus_out)` 实现。
  - 要考虑到在后续的主轮询中，怎么把它从托盘平滑地 Bring to Front。

### Project Structure Notes

- `ui/dashboard_app.py`: 创建这个文件，在此封装完整的 Dashboard 类。
- `main.py` / `ui/tray_icon.py`: 如果要能从托盘打开此面板，请小心处理 Windows/Mac 下的 Tkinter mainloop 和 Pystray event loop 是否冲突。目前优先聚焦把 `dashboard_app.py` 写成组件，单独测试运行无白屏即可。

### Previous Story Intelligence & Git Patterns

- `3-1-desktop-system-tray-subsystem` 已构建了 `queue.Queue` 进行非阻塞交互，这说明如果我们需要 Dashboard 发起重试，最终也会复用这套 `Queue` 事件流。
- `3-2-bark-multi-tier-notifications` 演示了被动告警。Dashboard 是被动监控的可视化扩展，无需打扰用户，做到极高频快速的只开只关即可。

### References

- [Source: planning-artifacts/epics.md#Story 3.3: CustomTkinter HUD Dashboard]
- [Source: planning-artifacts/ux-design-specification.md#Design System Foundation]
- [Source: planning-artifacts/ux-design-specification.md#Component Strategy]
- [Source: planning-artifacts/architecture.md#Frontend Architecture (UI IPC & GUI Framework)]

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Debug Log References
- Pipeline test suite executed via `pytest tests/` successfully (74 passed in ~23s).
- Verified `test_dashboard_app.py` mocks to bypass CI blocking.
- Installed `customtkinter` dependency.

### Completion Notes List
- ✅ Implemented `DashboardApp` in `ui/dashboard_app.py` leveraging `customtkinter` to maintain footprint < 100MB.
- ✅ Successfully handled the FocusOut logic using `withdraw()` and `deiconify()` mappings.
- ✅ Built `PipelineStatusCard` to decouple state updates and added error-state action button layouts.
- ✅ HUD panel features responsive `CTkProgressBar` and dynamic color styling referencing AC metrics.

### File List
- requirements.txt
- ui/dashboard_app.py
- tests/test_dashboard_app.py

### Change Log
- Added `customtkinter` dependency.
- Scaffolded comprehensive CustomTkinter dashboard implementation and automated headless test suite.

---
Ultimate context engine analysis completed - comprehensive developer guide created
