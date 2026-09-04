# Sparse Checkout Clone (Plan F)

**Goal:** Stop materializing whole repositories in the store when only a handful of skill directories are needed. Clone without checkout, discover skill directories from the git tree, then sparse-checkout only those directories.

**Background:** Benchmark on `herdrdev/herdr` (2851 files, 5 skills):

| Strategy | Time | Disk |
|---|---|---|
| `--filter=blob:none` (current default) | 4.5s | 48M |
| `--filter=blob:none --depth 1` (current `shallow`) | 4.9s | 46M |
| `--no-checkout` + `ls-tree` discovery + sparse-checkout | 4.0s | 636K |

`--filter=blob:none` alone barely helps: checking out HEAD still fetches every blob of the current tree. The win comes from never checking out directories that contain no skill.

**Architecture:** Partial clone already fetches all tree objects, so `git ls-tree -r HEAD` works offline right after a `--no-checkout` clone. Reuse the existing detection rules (root singleton, `skills/` dir, `skills_dir`, skip `_*`, stop descending at the first `SKILL.md`) on that path list to pick the sparse set. The store stays a real git repo, so `check-updates`, `update`, `git fetch` and `git log` keep working unchanged. Re-apply the sparse set after every pull so skills added upstream get materialized.

**Tech Stack:** git ≥ 2.37 (cone-mode `sparse-checkout`), Python 3.12, pytest.

---

## Task 1: Path-list skill discovery (TDD)

**Files:**
- Modify: `src/skm/detect.py`
- Modify: `tests/test_detect.py`

**Step 1: Write failing tests** for `select_skill_dirs(paths, skills_dir) -> list[str] | None`:

- root `SKILL.md` → `None` (full checkout)
- `skills/a/SKILL.md`, `skills/b/SKILL.md`, `other/x.py` → `['skills/a', 'skills/b']`
- no `skills/` dir → walk from root: `foo/SKILL.md`, `bar/baz/SKILL.md` → `['bar/baz', 'foo']`
- directory starting with `_` is skipped at every level
- nested skill inside a skill is not listed (stop descending)
- `skills_dir='pkg/curated'` → only dirs under it; `skills_dir` that is itself a skill → `[skills_dir]`
- `skills_dir` with no `SKILL.md` below → `[]`
- no `SKILL.md` anywhere → `[]`

**Step 2: Implement** `select_skill_dirs` in `detect.py`, sharing the same rules as `detect_skills` / `_walk_for_skills`. Paths are repo-relative POSIX strings of blobs.

**Step 3:** `uv run pytest tests/test_detect.py -v` passes.

## Task 2: Sparse clone in git.py (TDD)

**Files:**
- Modify: `src/skm/git.py`
- Modify: `tests/test_git.py`

**Step 1: Write failing tests**

- Update the two `fake_run_cmd` command-sequence tests: clone now emits
  `git clone --filter=blob:none [--depth 1] --no-checkout <url> <dest>`, then `git ls-tree -r -z HEAD`, then `git sparse-checkout set --cone <dirs>` (or `git sparse-checkout disable` when no dirs / root singleton), then `git checkout`. The fake returns ls-tree output listing `skills/a/SKILL.md` so the sparse path is exercised.
- Real local-repo test: source repo with `skills/a/SKILL.md`, `skills/b/SKILL.md`, `big/blob.bin`, `README.md`. After `clone_or_pull`: `skills/a` and `skills/b` exist, `big/` does not, `git sparse-checkout list` contains both dirs.
- Real local-repo test: add `skills/c/SKILL.md` upstream, call `clone_or_pull` again → `skills/c` now exists in dest.
- Real local-repo test: singleton repo (root `SKILL.md` plus `docs/x.md`) → full checkout, `docs/x.md` exists.
- Real local-repo test: `skills_dir='pkg'` → only `pkg/*` skill dirs checked out.

**Step 2: Implement**

- `list_tree_files(repo_path) -> list[str]`: parse `git ls-tree -r -z HEAD`, return paths of blobs, skipping symlinks (mode `120000`) and submodules (type `commit`).
- `apply_sparse_checkout(repo_path, skills_dir) -> list[str] | None`: `dirs = select_skill_dirs(list_tree_files(...), skills_dir)`; if `dirs` is `None` or empty → `git sparse-checkout disable`; else `git sparse-checkout set --cone <dirs>`. Returns `dirs`.
- `clone_or_pull(repo_url, dest, clone_strategy=None, skills_dir=None)`:
  - existing repo: `git pull --ff-only` then `apply_sparse_checkout`.
  - new repo: clone with `--no-checkout`, `apply_sparse_checkout`, then `git checkout`.

**Step 3:** `uv run pytest tests/test_git.py -v` passes.

## Task 3: Thread `skills_dir` through commands

**Files:**
- Modify: `src/skm/commands/install.py` (two `clone_or_pull` call sites)
- Modify: `src/skm/commands/update.py` (one call site)
- Modify: `tests/test_cli_e2e.py`

**Step 1: Write failing e2e tests**

- `install` on a repo containing `skills/a` and an unrelated `big/` dir: store repo has `skills/a`, lacks `big/`, skill is linked, lock recorded.
- After upstream adds `skills/b`, `update --all` materializes `skills/b` and links it.

**Step 2:** Pass `skills_dir=repo_config.skills_dir` at every `clone_or_pull` call.

**Step 3:** `uv run pytest -v` (full suite) passes.

## Task 4: Docs

**Files:**
- Modify: `README.md` (`clone_strategy` paragraph → describe sparse clone; note that existing caches shrink on next `skm update`)
- Modify: `AGENTS.md` (architecture line, `git.py`/`detect.py` descriptions, install command description)

## Task 5: Commit

Run the full suite once more, then commit with a message describing the sparse checkout clone.

---

## Decisions and caveats

- **Existing caches are not rewritten by `install`.** `install` skips the pull for already-cloned repos, so legacy full clones only shrink on the next `update` (which pulls and re-applies the sparse set). Documented in README.
- **Cone mode keeps top-level files of ancestor directories** (e.g. `README.md`, `skills/README.md`). This is small and keeps `detect_skills` behaviour identical: it only walks directories that exist.
- **Skills referencing files outside their own directory** (`../../docs/x.md`) will break under sparse checkout. The `skills` CLI has the same limitation because it copies only the skill directory. `clone_strategy` is left in place; a future `full` value could opt out if this ever matters.
- **`skills`/`skills_excludes` filters are not used to narrow the sparse set.** Skill names live in frontmatter, which needs blob content; all detected skill dirs are small anyway and the lock/stale logic expects full detection.
- **No `--reclone` flag.** Out of scope; `rm -rf` of the store dir followed by `skm install` achieves the same.
