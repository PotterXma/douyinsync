# documents/

本仓库将 **设计与规范正文** 放在 **`docs/`**（历史路径），本目录仅作 **Newegg / BMAD 规范中的 `documents/` 占位与入口**。

请阅读：

- [项目文档索引](../docs/index.md)
- [BMAD 文档流程与仓库对齐](../docs/bmad-documentation-alignment.md)（`bmad-document-project` 技能与 `_bmad/bmm/config.yaml` 映射）
- [BMAD 产出索引](../_bmad-output/README.md)

完整业务若需按规范归档为 `<项目号>_<业务简称>_YYYYMMDD.mdc`，请将文件放在本目录或 `docs/` 下由团队约定；日常技术说明以 `docs/*.md` 为准。

持续集成：**`.github/workflows/ci.yml`**（Windows，Python 3.10–3.13，pytest）；依赖机器人 **`.github/dependabot.yml`**。详见 **`tests/test-summary.md`**。
