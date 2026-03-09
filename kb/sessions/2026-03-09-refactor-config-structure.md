---
created: 2026-03-09
tags:
  - refactor
  - config
  - agents
---

# 重构配置文件结构，支持 agents.default 全局配置

## 概要

将 `skills.yaml` 配置文件从扁平的 YAML 列表格式重构为字典格式。原来的 repo 配置列表移入 `packages:` 键下，新增 `agents.default:` 键用于全局指定默认启用的 agents（从 KNOWN_AGENTS 中选取）。每个 package 的 `agents.includes/excludes` 在 default 的基础上进一步过滤。重构涉及类型定义、配置加载、CLI 入口、命令实现和所有相关测试。

## 修改的文件

- `src/skm/types.py` — 新增 `DefaultAgentsConfig` 和 `SkmConfig` 两个 Pydantic 模型，`DefaultAgentsConfig` 包含 `default` 字段及对 KNOWN_AGENTS 的校验
- `src/skm/config.py` — `load_config` 返回类型从 `list[SkillRepoConfig]` 改为 `SkmConfig`，要求 YAML 根节点为 dict
- `src/skm/cli.py` — `_expand_agents` 新增 `default_agents` 参数用于过滤；`install`、`update`、`list --all` 命令先加载配置再传入过滤后的 agents
- `src/skm/commands/install.py` — `run_install` 参数从 `config_path` 改为 `config: SkmConfig`，遍历 `config.packages`
- `src/skm/commands/update.py` — `run_update` 参数从 `config_path` 改为 `config: SkmConfig`，遍历 `config.packages`
- `skills.example.yaml` — 重构为新的字典格式，包含 `agents.default` 和 `packages`
- `tests/test_config.py` — 更新示例 YAML 为新格式，新增 `agents.default` 和未知 agent 校验测试
- `tests/test_install.py` — 配置写入改为新格式，使用 `load_config` 加载后传入
- `tests/test_cli_e2e.py` — `_write_config` 辅助函数改为生成 `{"packages": ...}` 格式

## Git 提交记录

本次 session 无 git 提交（改动尚未提交）。

## 注意事项

- 配置加载从 CLI 层提前执行（而非在 command 内部），这样 `agents.default` 可以在 `_expand_agents` 中生效，command 函数接收已处理好的 config 和 agents
- 未保留旧列表格式的向后兼容，用户需手动迁移配置文件
- `DefaultAgentsConfig.default` 字段有校验器，确保所有值都是 `KNOWN_AGENTS` 的合法 key
