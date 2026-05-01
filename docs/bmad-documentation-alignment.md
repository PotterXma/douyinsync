# BMAD 文档流程与仓库对齐说明

> **最后更新**: 2026-04-25（与 README / AGENTS / 各 `docs/` 同步一轮）| 对应 Cursor 技能 **`bmad-document-project`** 与 BMM 配置

本文说明：**BMAD 方法论要求产出什么**、**在本仓库落在哪里**、**日常改代码应同步改哪些文档**，避免规划与实现脱节。

---

## 1. 权威配置：`_bmad/bmm/config.yaml`

| 键 | 本仓库路径 | 用途 |
|----|------------|------|
| `planning_artifacts` | `./_bmad-output/planning-artifacts` | PRD 快照、Epic/Story、追溯矩阵、实现就绪报告等 |
| `implementation_artifacts` | `./_bmad-output/implementation-artifacts` | `sprint-status.yaml`、装配说明、`stories/*.md` |
| `project_knowledge` | `./docs/project-context.md` | **AI 与开发者的硬约束**（守则、禁止项、路径约定） |
| `communication_language` / `document_output_language` | `zh-CN` | 规划类与回复语言 |

> 说明：`project_knowledge` 在 BMM 中指向 **单文件** `project-context.md`；BMAD `document-project` 技能模板里若出现「`{project_knowledge}/index.md`」类路径，在本仓库应以 **`docs/index.md`** 为工程文档总索引理解。

---

## 2. `bmad-document-project` 工作流（技能路径）

技能根目录：`.cursor/skills/bmad-document-project/`。

| 顺序 | 文件 | 作用 |
|------|------|------|
| 1 | `SKILL.md` | 入口：转 `workflow.md` |
| 2 | `workflow.md` | 加载 `_bmad/bmm/config.yaml`，转 `instructions.md` |
| 3 | `instructions.md` | 路由：是否存在 `project-scan-report.json`、是否已有 `index.md`，选择 **initial_scan / full_rescan / deep_dive** |
| 4 | `workflows/full-scan-workflow.md` | 全量扫描子流程 |
| 5 | `workflows/full-scan-instructions.md` | 分步执行（项目分型、栈分析、写 `project-overview`、架构、索引等） |
| 6 | `checklist.md` | 自检清单（扫描深度、索引完整性、Brownfield PRD 就绪等） |

**本仓库已具备的 BMAD 对齐产出**（不必从零重复全扫描，除非做大重构）：

- `docs/index.md` — 总索引  
- `docs/project-overview.md`、`architecture.md`、`data-models.md`、`api-contracts.md`、`component-inventory.md`、`development-guide.md`  
- **本次补全**：`source-tree-analysis.md`、`deployment-guide.md`、本文  

---

## 3. 三类文档的分工

| 类型 | 位置 | 何时更新 |
|------|------|----------|
| **工程权威** | `docs/*.md` | 任何影响行为、配置、数据流、部署的合并；至少更新 `architecture` / `development-guide` 相关小节，并 bump `index.md` 日期 |
| **BMAD 规划** | `_bmad-output/planning-artifacts/` | 需求变更、Epic 拆分、PRD 修订、实现就绪评审 |
| **故事与冲刺** | `_bmad-output/implementation-artifacts/` | 每个可验收故事：`stories/<id>.md` + `sprint-status.yaml`；Retro 写入 `planning-artifacts/RETROSPECTIVES.md` |

---

## 4. `documents/` 目录（组织规范）

根据仓库级 **Newegg / 工程规范**：`documents/` 为 **合规入口**，正文维护在 **`docs/`**（见 `documents/README.md`）。  
完整业务归档若需 `.mdc`，命名约定见工作区规则；本项目的日常技术说明以 `docs/` Markdown 为主。

---

## 5. 最小合入检查（轻量 BMAD Gate）

合并前建议自查：

1. **测试**：`python -m pytest tests/ -q` 通过。  
2. **文档**：`docs/index.md` 是否需更新链接或日期；是否触及架构/部署/配置。  
3. **故事**：若对应 `_bmad-output` 中已有 Story，是否在 `stories/*.md` 或 sprint 状态中体现结论。  

---

## 6. 延伸阅读

- [README.md](../README.md) — 用户向快速上手与子命令（已与 `docs/` 互链）  
- [AGENTS.md](../AGENTS.md) — Cursor Agent 文档入口  
- [_bmad-output/README.md](../_bmad-output/README.md) — 产出根索引  
- [planning-artifacts/README.md](../_bmad-output/planning-artifacts/README.md) — 规划类导航  
- [project-context.md](./project-context.md) — AI 协作硬约束  
