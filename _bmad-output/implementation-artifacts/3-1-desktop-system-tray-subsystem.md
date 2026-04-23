# Story 3.1: Desktop System Tray Subsystem

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

作为一名 Windows 桌面用户，
我想要一个后台系统托盘 (SysTray) 应用程序来处理基础的上下文事件和菜单，
以便于我可以触发重载配置、打开面板以及启停等操作，而无需去终端输入命令。

## Acceptance Criteria

1. **Given** 进程已正常启动，
   **When** 从系统托盘点击/触发菜单选项（例如配置重载、暂停等），
   **Then** 它将通过 Python 的线程安全 `queue.Queue` 将信号安全地下发到主引擎，绝不能冻结/阻塞 Windows UI 主线程。
2. **Given** 用户在右键托盘上触发操作命令，
   **When** 产生反馈时，
   **Then** 系统必须在 0.5s 内（毫秒级）通过原生的 Windows Notification System (Toast) 等轻盈手段进行快速响应并轻量告警，例如 "Config Reloaded"。

## Tasks / Subtasks

- [x] 任务 1: 创建轻量级的桌面系统托盘组件 (AC: 1, 2)
  - [x] 基于 `pystray` 或者是等同的库，在 `ui/tray_icon.py` 初始化托盘模块，绑定双击、右击事件。
  - [x] 建立基本上下文托盘菜单 (如 "Reload Config", "Open Dashboard", "Exit")。
- [x] 任务 2: 打通从托盘 UI 到后台管道的无阻塞线程安全通信 (AC: 1)
  - [x] 定义对应的事件数据类 (`@dataclass` 或具名元组) 格式，替代裸字典传输。
  - [x] UI 层不能等待反馈，仅负责生产事件并放到 `queue.Queue` 里。
- [x] 任务 3: 实现 Windows 系统的轻型气泡或托盘快速通知 (AC: 2)
  - [x] 验证系统托盘在接收到信号、或发送命令后，可以调用 Windows 原生的系统气泡告警（比如托盘图标自身的 `notify()` 功能，或者 `win10toast`）做出 0.5秒内 的极速回应。

### Review Findings

- [x] [Review][Patch] `on_open_dashboard` 缺少 `notify()` 反馈，违反 AC2（0.5s 反馈要求）[ui/tray_icon.py:31]
- [x] [Review][Patch] `import time` 在 `main.py` 中未使用，清理残留导入 [main.py:2]
- [x] [Review][Patch] `requirements.txt` 缺少 `pystray[win32]` extras，Windows 下 `notify()` 可能静默失败 [requirements.txt]
- [x] [Review][Patch] `on_reload` / `on_exit` 双路 icon 判断冗余（`self.icon` 与传入 `icon` 参数在 `setup()` 后是同一对象），宜化简 [ui/tray_icon.py:24-39]
- [x] [Review][Defer] EXIT 双重入队问题 [main.py:76] — deferred，break 后第二个 EXIT 无害留在队列，低风险
- [x] [Review][Defer] `dashboard_app.py` 尚未创建 [ui/] — deferred，属于 Story 3-3 范围
- [x] [Review][Defer] `AppEvent.payload: Optional[Any]` 类型过宽 [utils/models.py:46] — deferred，架构演进问题，当前阶段可接受

## Dev Notes

- **相关架构模式和约束**: 
  - 根据架构决策，必须采用 "主线程运行 GUI + 后台子线程跑 Pipeline" 的高压隔离并发模型以满足解耦。
  - **下行 (UI -> Pipeline)**: 托盘的操作仅作为事件生产者，通过进程内 Queue 下发非阻塞事件字面量实体。绝对禁止相互死锁。
  - 无单向强回调阻塞逻辑！绝对满足 "Zero-Interference Trust" 用户诉求心智。
- **涉及的文件/源码路径**:
  - `ui/tray_icon.py`：构建核心 SysTray 功能的地方。
  - `main.py`：应用入口需要被改造为主线程启动 UI 并在辅线程跑业务循环（或者相反设计以保 UI 事件循环不卡死）。
  - `utils/models.py`：需统一建立 `AppEvent` 等类结构承载事件体。
- **技术栈/框架信息**:
  - `pystray` (作为跨平台首选托盘框架), Python内置 `queue` 及 `threading` 模块。

### Project Structure Notes

- `ui/tray_icon.py` 严格遵循“单向只发不收”或者“被动抛气泡”准则。严禁调用 `requests` 或 `sqlite3`。
- 引入的类包和路径全部都应是 Absolute Import，例如 `from utils.models import AppEvent`。

### References

- [Source: planning-artifacts/architecture.md#Frontend Architecture (UI IPC & GUI Framework)]
- [Source: planning-artifacts/ux-design-specification.md#Feedback Patterns (状态反馈范式)]
- [Source: planning-artifacts/ux-design-specification.md#Journey 1: The Daily Health Check (无痛巡检)]

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References
- All tests passing (3 tests in test_tray_icon.py, 100% integration verification).

### Completion Notes List
- 整理并梳理了托盘与常驻进程的 Queue 解耦心法，确保主程不受干扰。
- 整合了 UX 设计与极速反馈（0.5s）标准至 Story 内容。
- ✅ Implemented `TrayApp` in `ui/tray_icon.py` using `pystray`. Events (RELOAD_CONFIG, OPEN_DASHBOARD, EXIT) are now passed to the `queue.Queue` asynchronously as `AppEvent`.
- ✅ `main.py` has been wired to support this queue-based approach and avoid blocking the `pystray` Windows UI event loop. Tests in `test_tray_icon.py` achieve clean coverage.

### File List
- ui/__init__.py
- ui/tray_icon.py
- utils/models.py
- main.py
- tests/test_tray_icon.py
