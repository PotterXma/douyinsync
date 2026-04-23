# Epic 回顾（Retrospectives）— 已全部完成（补档）

> 对应 `../implementation-artifacts/sprint-status.yaml` 中 `epic-*-retrospective: done`。

## Epic 1 — 守护进程与托盘

- **继续保持**：主线程托盘 + 后台管道分离清晰。
- **改进已吸收**：子进程拉起 Dashboard / 设置 / 统计，避免阻塞托盘。

## Epic 2 — 数据层

- **继续保持**：WAL + DAO 单一路径；聚合查询支撑 UI。
- **改进已吸收**：`videolib` 已改为 `VideoDAO`/`AppDatabase`，消除直连 SQLite 技术债。

## Epic 3 — 抓取与下载

- **继续保持**：分块流式与签名链路基线。
- **风险**：抖音 Cookie/WAF 变更需运营侧更新；代码侧保持可测扩展点。

## Epic 4 — 上传与韧性

- **继续保持**：OAuth 续传与配额熔断组合。
- **后续可选**：收敛 `asyncio.iscoroutinefunction` 弃用告警（Python 3.14+）。

## Epic 5 — UI

- **继续保持**：CTk HUD 只读、经典库写操作隔离在 `videolib`。
- **后续可选**：打包 exe 下全量子命令回归清单写入 `README`。
