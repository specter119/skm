---
created: 2026-09-04
tags:
  - sparse-checkout
  - git
  - clone
  - detect
  - vercel-skills
  - research
---

# 调研 vercel-labs/skills 的下载策略，并为 skm 实现 sparse-checkout 克隆

## 概要

起因是担心 skm 从大型 monorepo 安装技能时需要把整个仓库克隆下来，代价太高。先调研了 `vercel-labs/skills`（`npx skills add`）的实现：对普通仓库它同样是整仓 `git clone --depth 1` 到临时目录再复制技能目录；只有白名单 owner（vercel、vercel-labs、heygen-com、zapier/connectors）走一条不经 git 的 blob 快速路径（GitHub Trees API 列树、raw.githubusercontent.com 读 frontmatter、skills.sh 下载预打包快照），另外支持直接下载 raw SKILL.md 或 tar/zip 链接。

在 `herdrdev/herdr`（2851 个文件、5 个技能）上实测发现 skm 原有的 `--filter=blob:none` 对减小体积几乎无效：checkout HEAD 时仍要拉取当前树的全部 blob，工作区照样 46MB。真正有效的是不 checkout 无关目录。于是实现了方案 F：`--filter=blob:none --no-checkout` 克隆后，用 `git ls-tree -r -z HEAD` 离线列树，按 skm 既有的技能检测规则选出技能目录，`git sparse-checkout set --cone` 后再 `git checkout`；每次 pull 后重新计算 sparse 集合。端到端验证 store 从 48MB 降到 2.9MB（加 `clone_strategy: shallow` 可再降到约 600KB），146 个测试全部通过，已提交为 `0d44a2f`。

## 修改的文件

- `kb/plans/2026-09-04-sparse-checkout-clone.md` — 新建。含基准数据、五个任务的拆分、设计取舍与已知限制。
- `src/skm/detect.py` — 新增 `select_skill_dirs(paths, skills_dir)` 与 `_select_under()`，对路径列表套用与 `detect_skills` 相同的规则（根单例、`skills/` 优先、`skills_dir`、跳过 `_*` 与 `.git`、遇到 SKILL.md 停止下钻）。根单例返回 `None` 表示全量 checkout。
- `src/skm/git.py` — `clone_or_pull` 新增 `skills_dir` 参数，克隆改为 `--no-checkout`；新增 `list_tree_files()`（解析 `ls-tree -z`，跳过符号链接与子模块）和 `apply_sparse_checkout()`（无技能或根单例时 `sparse-checkout disable`）。已有仓库在 `git pull --ff-only` 后也重新应用 sparse 集合。
- `src/skm/commands/install.py`、`src/skm/commands/update.py` — 三处 `clone_or_pull` 调用传入 `skills_dir=repo_config.skills_dir`。
- `tests/test_detect.py` — 新增 9 个 `select_skill_dirs` 用例。
- `tests/test_git.py` — 重写两个命令序列用例（含根单例走 `disable` 的用例），新增 5 个真实本地仓库用例：只 checkout 技能目录、pull 后出现新技能、根单例全量、`skills_dir` 生效、旧全量克隆在 pull 后收缩。
- `tests/test_cli_e2e.py` — 新增 `TestSparseCheckout` 三个端到端用例；`fake_clone_or_pull` 签名补上 `skills_dir`。
- `tests/test_install.py` — `fake_clone_or_pull` 签名补上 `skills_dir`。
- `README.md` — 重写 clone 策略段落，说明 sparse 行为、`shallow` 的新含义、旧缓存在下次 `update` 收缩。
- `AGENTS.md` — 架构行、`detect.py`/`git.py` 描述、`skm install` 描述更新，新增 "Sparse Clone" 小节。

## 注意事项

- **`--filter=blob:none` 不减小工作区。** 它只延迟历史版本的 blob，checkout HEAD 仍需全部当前 blob。想省流量必须配合 sparse-checkout，这是本次最重要的认知纠正。
- **partial clone 下 `git ls-tree` 是离线的。** blob:none 过滤的只是 blob，tree 对象总会被拉取，因此 `--no-checkout` 后立即 `ls-tree -r HEAD` 不产生网络请求，可以据此决定 sparse 集合。
- **`select_skill_dirs()` 与 `detect_skills()` 必须保持同步。** 两者是同一套规则的两种实现（路径列表 vs 文件系统），改动检测规则时两处都要改，且 `test_detect.py` 两组用例都要更新。
- **cone 模式会保留祖先目录的顶层文件**（如根目录的 README、`skills/README.md`），体积很小，且保证 `detect_skills` 只会遍历真实存在的目录，行为与之前一致。
- **测试字符串里 `"\0100644"` 会被 Python 当作八进制转义 `\010`。** 构造 `ls-tree -z` 的假输出时要用 `\x00`。
- **skills CLI 的白名单快速路径依赖 skills.sh 中心化缓存**，实测该服务对非白名单仓库也返回 200，但对 skm 来说引入第三方服务不值得；tarball 方案虽最快但会丢掉 git 仓库，`check-updates`/`update` 的增量逻辑要全部重写，也不采用。
- **skills CLI 值得借鉴的另一点：** 它用 GitHub Trees API 做更新检查，按技能目录的 tree SHA 而非整仓 commit 判断是否有更新，上游改无关代码时不会误报。

## 遗留问题

- 本机 `~/.local/share/skm/skills/` 下的旧缓存不会被 `install` 收缩，需要跑一次 `skm update --all`。
- 技能 SKILL.md 若引用自身目录之外的文件（如 `../../docs/x.md`），sparse 后会断链。skills CLI 有同样限制。若将来遇到，可给 `clone_strategy` 加 `full` 值退出 sparse。
- `herdrdev/herdr` 在 `.agents/skills/` 下还有 3 个技能，但 skm 检测规则在存在 `skills/` 目录时只看 `skills/`，因此未发现。skills CLI 会同时扫描 `.agents/skills/`、`.claude/skills/` 等一组约定目录，可作为后续改进。
- `check-updates` 仍按整仓 commit 判断更新，可考虑借鉴按技能目录 tree SHA 比较的做法（`git rev-parse HEAD:<dir>` 即可，无需 GitHub API）。
- 调研用的 `tmp/vercel-skills/` 克隆仍留在工作目录（未纳入 git），不需要时可删除。

## 相关文档

- [Sparse Checkout Clone (Plan F)](../plans/2026-09-04-sparse-checkout-clone.md) — 本次 session 新建并按此计划实现
