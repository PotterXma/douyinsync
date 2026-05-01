# DouyinSync — Agent 说明（Cursor）

## 文档

- 入口：[docs/index.md](docs/index.md)
- BMAD 流程与仓库映射：[docs/bmad-documentation-alignment.md](docs/bmad-documentation-alignment.md)
- 部署与打包：[docs/deployment-guide.md](docs/deployment-guide.md)
- 源码树：[docs/source-tree-analysis.md](docs/source-tree-analysis.md)
- BMAD 规划：[_bmad-output/planning-artifacts/README.md](_bmad-output/planning-artifacts/README.md) · [sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml)

## Skills

- 项目内 BMAD 等技能目录：`.cursor/skills/`（各子目录内 `SKILL.md`）
- 勿使用 `~/.cursor/skills-cursor/` 存放本项目自定义技能（该目录为 Cursor 内置技能保留）

## 测试

- 安装：`pip install -r requirements-dev.txt`
- 运行：`python -m pytest tests/`（配置见仓库根 **`pytest.ini`**，`asyncio_mode=auto`）
- CI：`.github/workflows/ci.yml`，Windows，Python **3.10–3.13** 矩阵；依赖 PR 见 **`.github/dependabot.yml`**

## 约定

- 语言：与用户对话默认使用简体中文（除非用户改用其他语言）。
- 代码与测试：遵循 `docs/project-context.md` 与 `docs/development-guide.md`。
