# Story 4.2: Pre-flight Network Probe & Transient Retry Decorator

**Status:** ready-for-dev
**Epic:** 4 — Automated Background Scheduling & Resilience
**Story ID:** 4.2
**Story Key:** 4-2-preflight-network-probe-retry-decorator

---

## 📖 Story

As a resilient pipeline,
I want to verify network connectivity before each sync cycle and retry transient failures automatically,
So that temporary network drops do not cause permanent failures or misleading error states.

---

## ✅ Acceptance Criteria

1. **Given** the scheduler triggers a pipeline run
   **When** the pre-flight probe detects no network connectivity
   **Then** the current run cycle is skipped with a warning log and no state is mutated.

2. **Given** network drops during YouTube upload or video/cover download
   **When** an external network exception triggers
   **Then** the existing `@auto_retry` decorator safely retries failed operations up to 3 times with exponential backoff before bubbling up the failure.

3. **Given** a failed pipeline execution triggered by network reasons
   **When** yielding the final state
   **Then** the exception is correctly mapped to `give_up` or standard retry state without crashing the main loop.

---

## 🧠 关键背景 (Developer Context)

### 🏗️ 架构合规要求 (Architecture Compliance)
- **Retry Mechanism**: 根据架构规定，重试机制必须**无侵入**，需利用现有的 `utils.decorators.auto_retry` (`@auto_retry`) 作为拦截点。不要重新发明轮子。
- **Split-Tunneling / Dual Path**: 探针应该能够分别验证直连通道（如 Douyin 端点或 DNS，无代理）与代理通道（如 YouTube 端点，走代理），也可以合并为一次强壮的 ping。推荐使用异步轻量探针，不要执行真实复杂的 API 操作。
- **Data Pattern**: 在放弃任务导致 `failed` 状态时，必须使用 `VideoDAO` 封装，不可直写 SQL。并且不要在探针中产生任何脏状态。

### 📁 技术与包依赖 (Library Framework Requirements)
- **httpx**: 网络探测必须使用异步 `httpx.AsyncClient` 发起非阻塞探测，设置较短的超时时间（例如 `timeout=5.0`）。绝不可使用阻塞风格的 `requests` 或 `os.system('ping')`。
- **Type Hinting**: 所有新增组件参数及返回值必须加注明确类型（Type Hinting）。

### 📍 文件路径与实现要求 (File Structure)
- 可新建文件 `utils/network.py` 来封装一个高内聚的网络探针函数，具备类似签名 `async def preflight_network_check() -> bool:`。
- 修改 `modules/scheduler.py`：在 `PipelineCoordinator._run_async_cycle` 进入核心主干逻辑（比如查询数据库准备上传）之前，优先调用该网络探测器。若返回 False 直接 `return` 结束本轮 Cycle。
- 修改 `modules/youtube_uploader.py` 与 `modules/downloader.py`：
  - 检查它们向外暴露的 HTTP 调用是否缺少容错保护。
  - 为下载函数及上传核心函数挂载 `@auto_retry(max_retries=3)` 装饰器。

### 🧪 测试防线 (Testing Requirements)
- 新增/修补测试 `tests/test_scheduler.py`，必须覆盖探针失败时 Pipeline 是否执行了“防雪崩短路返回”（可用 `AsyncMock` 模拟 `preflight_network_check` 返回 `False`）。
- 需复用已存在于 `conftest.py` 中的 Mock fixtures 工厂，保持所有依赖注入结构可测。

---

## 🔮 前期智能与经验教训 (Previous Story Intelligence)

1. **并行安全**：在 Story 4.1 中我们已经为 Pipeline 搭建了 `threading.Lock` 防冲突启动。网络探针的引入处于获取该锁的保护周期之内，请确保即使探针网络超时抛异常，`_run_async_cycle` 也通过正确的 context 保证最后释放调度锁。
2. **惰性日志 (Lazy Logging)**：之前的 Code Review 里着重强调日志的规范安全——必须贯彻 `logger.warning("network reachable probe failed: %s", exc)` 格式，禁止将变量写入 `f-string` 内。

---

## 🧑‍💻 开发任务列表 (Dev Tasks)

- [ ] **Task 1: 实现 Network Probe 探针组件** (`utils/network.py`)。使用 httpx 并引入代理隔离思路。
- [ ] **Task 2: 在外发模块补全 Retry Decorator**。深入 `downloader.py` / `youtube_uploader.py`，把 `@auto_retry` 赋予所有容易发生 Timeout 的核心下载和上传异步函数。
- [ ] **Task 3: 集成探针至 Pipeline Coordinator**。在 `modules/scheduler.py` 的处理流水线首部接入探针判定逻辑。
- [ ] **Task 4: 添加防雪崩单元测试**。确保涵盖网络不通场景的 0 数据库操作动作。

