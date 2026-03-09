# SKM - Skill Manager

A CLI tool that manages AI agent skills by cloning GitHub repos, detecting skills via `SKILL.md`, and symlinking them to agent directories based on a central YAML config.

## Tech Stack

- Python 3.12+, uv, click, pyyaml, pydantic
- Git operations via subprocess
- Tests: pytest

## Project Structure

```
src/skm/
├── cli.py              # Click CLI entry point (group + subcommands)
├── types.py            # Pydantic data models + constants
├── config.py           # Load skills.yaml → list[SkillRepoConfig]
├── lock.py             # Read/write skills-lock.yaml
├── detect.py           # Walk cloned repos for SKILL.md files
├── git.py              # Clone, pull, fetch, commit SHA helpers
├── linker.py           # Symlink skills to agent dirs, resolve includes/excludes
└── commands/
    ├── install.py      # Clone repos, detect skills, link to agents, update lock
    ├── list_cmd.py     # Print installed skills from lock file
    ├── check_updates.py # Fetch remotes, compare commits, show available updates
    └── update.py       # Pull latest for a skill's repo, re-link, update lock
tests/
├── test_types.py        # Pydantic model validation
├── test_config.py       # Config loading, error handling
├── test_lock.py         # Lock file I/O
├── test_detect.py       # Skill detection logic
├── test_git.py          # Git operations (clone, commit retrieval)
├── test_linker.py       # Symlink creation, agent filtering
├── test_install.py      # Install command unit tests
└── test_cli_e2e.py      # End-to-end CLI tests for all commands
```

## Key Paths

- **Config:** `~/.config/skm/skills.yaml` — user-defined list of repos and skills to install
- **Lock:** `~/.config/skm/skills-lock.yaml` — tracks installed skills, commits, symlink paths
- **Store:** `~/.local/share/skm/skills/` — cloned repos cached here
- **Agent dirs:** Skills are symlinked into each agent's skill directory (e.g. `~/.claude/skills/`, `~/.codex/skills/`)

## Architecture

Config-driven: parse `skills.yaml` → clone repos to store → detect skills by walking for `SKILL.md` → symlink to agent dirs → write lock file.

Each command function (`run_install`, `run_list`, etc.) accepts explicit paths and agent dicts as parameters, making them testable with `tmp_path` fixtures without touching real filesystem locations.

## CLI Commands

- `skm install` — Clone repos, detect skills, create symlinks, update lock
- `skm list` — Show installed skills and their linked paths from lock file
- `skm check-updates` — Fetch remotes, compare against locked commits, show changelog
- `skm update <skill_name>` — Pull latest for a skill's repo, re-link, update lock

## Config Format (skills.yaml)

```yaml
- repo: https://github.com/vercel-labs/agent-skills
  skills:                    # optional: filter to specific skills (omit = all)
    - react-best-practices
  agents:                    # optional: control which agents get this skill
    excludes:
      - openclaw
- repo: https://github.com/blader/humanizer   # installs all detected skills to all agents
```

## Skill Detection

A skill is a directory containing a `SKILL.md` file with YAML frontmatter including a `name` field. Detection order:
1. Root `SKILL.md` → singleton skill (the repo itself is the skill)
2. `./skills/` subdirectory exists → walk its children
3. Otherwise → walk all subdirectories from repo root
4. Stop descending once `SKILL.md` is found (no nested skill-in-skill)

## Known Agents

Defined in `src/skm/types.py` as `KNOWN_AGENTS`:
- `standard` → `~/.agents/skills`
- `claude` → `~/.claude/skills`
- `codex` → `~/.codex/skills`
- `openclaw` → `~/.openclaw/skills`

## Testing

### Running Tests

```bash
uv sync
uv run pytest -v              # all tests
uv run pytest tests/test_cli_e2e.py -v   # e2e only
uv run pytest -k "install" -v            # filter by name
```

### Test Isolation

All tests run entirely within pytest's `tmp_path` — no real agent directories, config files, or git repos are touched. This is achieved two ways:

- **Unit tests** (`test_install.py`, `test_linker.py`, etc.): call `run_*` functions directly with explicit `config_path`, `lock_path`, `store_dir`, and `known_agents` parameters pointing to `tmp_path` subdirectories.
- **E2E tests** (`test_cli_e2e.py`): invoke the CLI through Click's `CliRunner` with `--config`, `--store`, `--lock`, and `--agents-dir` flags to redirect all I/O into `tmp_path`.

Git repos used in tests are local repos created via `git init` inside `tmp_path` — no network access required.

### CLI Path Overrides

The CLI group accepts four flags to override default paths, useful for both testing and safe manual experimentation:

```bash
skm --config /tmp/test.yaml \
    --store /tmp/store \
    --lock /tmp/lock.yaml \
    --agents-dir /tmp/agents \
    install
```

- `--config` — path to `skills.yaml` (default: `~/.config/skm/skills.yaml`)
- `--lock` — path to `skills-lock.yaml` (default: `~/.config/skm/skills-lock.yaml`)
- `--store` — directory for cloned repos (default: `~/.local/share/skm/skills/`)
- `--agents-dir` — base directory for agent symlinks; creates subdirs per agent name (overrides `KNOWN_AGENTS` paths)

### E2E Test Helpers

`test_cli_e2e.py` provides reusable helpers for writing new tests:

- `_make_skill_repo(base, repo_name, skills)` — creates a local git repo with specified skills. Each skill is `{"name": str, "subdir": bool}` where `subdir=True` (default) puts it under `skills/<name>/`, `False` makes it a singleton at repo root.
- `_cli_args(tmp_path)` — returns the common `--config/--store/--lock/--agents-dir` flags for full isolation.
- `_write_config(tmp_path, repos)` — writes a `skills.yaml` from a list of repo dicts.
- `_load_lock(tmp_path)` — loads the lock file as a plain dict for assertions.

### Writing New Tests

To add a new e2e test, follow this pattern:

```python
def test_my_scenario(self, tmp_path):
    repo = _make_skill_repo(tmp_path, "my-repo", [{"name": "my-skill"}])
    _write_config(tmp_path, [{"repo": str(repo)}])

    runner = CliRunner()
    result = runner.invoke(cli, [*_cli_args(tmp_path), "install"])

    assert result.exit_code == 0, result.output
    # assert on symlinks, lock contents, output text, etc.
```

## Development

```bash
uv sync
uv run pytest -v      # run tests
uv run skm --help     # run CLI
```

Do not run formatters or style linters on the code.
