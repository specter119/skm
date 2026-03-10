---
created: 2026-03-10
tags:
  - skm-install
  - cli
  - direct-source
  - interactive-selection
---

# 扩展 skm install 支持直接从源安装技能

## 概要

本次 session 为 `skm install` 命令添加了直接从 repo URL 或本地路径安装技能的能力。此前用户必须手动编辑 `skills.yaml` 配置文件才能添加新包，现在可以通过 `skm install <source> [skill_name]` 直接安装，支持交互式多选技能和 agent，并自动更新配置文件。

实现过程中遵循 BDD 方法，先编写了 14 个测试用例，再逐步实现功能。初始实现中存在一个问题：直接源安装后会调用 `run_install()` 重新安装所有已配置的包，经用户反馈后修复为仅安装当前指定的单个包（通过新增 `run_install_package()` 函数）。

## 修改的文件

- **`src/skm/tui.py`** — 新增 `interactive_multi_select()` 函数，支持复选框式多选交互（空格切换、回车确认、q 取消）
- **`src/skm/config.py`** — 新增 `save_config()` 将配置序列化为 YAML 并写入文件；新增 `upsert_package()` 按 source_key 匹配已有包并合并技能列表
- **`src/skm/cli.py`** — 扩展 `install` 命令，增加 `SOURCE`、`SKILL_NAME` 参数和 `--agents-includes`、`--agents-excludes` 选项；新增 `_find_package_by_source()` 和 `_source_matches()` 辅助函数
- **`src/skm/commands/install.py`** — 新增 `run_install_package()` 函数，用于安装单个包并将结果合并到已有 lock 文件中（不影响其他包的 lock 条目）
- **`tests/test_install_from_source.py`** — 新增 14 个 BDD 测试用例，覆盖本地路径安装、指定技能名安装、agents 标志、配置合并、取消选择、配置自动创建等场景

## Git 提交记录

本次 session 无 git 提交。

## 注意事项

- **单包安装 vs 全量安装**：直接源安装（`skm install <source>`）应仅安装指定的包，而非重新运行整个配置的安装流程。`run_install_package()` 通过合并 lock 文件条目实现这一点——保留其他源的条目，仅替换当前源的条目。
- **`upsert_package` 的 skills: None 语义**：当已有包配置 `skills: None`（表示安装所有技能）时，不应覆盖为具体技能列表。函数返回已有包对象，由调用方决定是跳过（已安装）还是重新安装（拉取新技能）。
- **测试中 mock 的位置**：`interactive_multi_select` 在 `skm.cli` 中被 import，所以 mock 路径应为 `skm.cli.interactive_multi_select` 而非 `skm.tui.interactive_multi_select`。
- **lock 文件合并逻辑**：需要同时按字面值和 expanduser 后的路径匹配 local_path，因为 lock 文件中存储的是 compact_path（带 `~`），而 source_key 是展开后的绝对路径。
