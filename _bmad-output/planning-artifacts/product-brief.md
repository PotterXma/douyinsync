# Product Brief — DouyinSync

## 问题陈述

抖音创作者内容需稳定、低人工地同步至 YouTube；境内网络与 API 配额使「一次性脚本」不可靠。

## 价值主张

- **无人值守**：托盘常驻 + 定时管道。
- **可恢复**：状态机、僵尸恢复、配额熔断、CDN 刷新。
- **可观测**：子进程 HUD、经典视频库、设置与统计。

## 目标指标（定性）

| 指标 | 方向 |
|------|------|
| 人工介入频率 | 趋近于配置变更与偶发纠错 |
| 数据一致性 | `douyin_id` 幂等、崩溃可自愈 |
| 可维护性 | 文档 + BMAD 追溯 + pytest |

## 范围外

见 `PRD-snapshot.md` 第 5 节。

## 相关文档

- [PRD-snapshot.md](./PRD-snapshot.md)
- [epics-and-stories.md](./epics-and-stories.md)
- [traceability-matrix.md](./traceability-matrix.md)
