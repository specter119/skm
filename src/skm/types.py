import os
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


# --- Config models (parsed from skills.yaml) ---


class AgentsConfig(BaseModel):
    includes: list[str] | None = None
    excludes: list[str] | None = None

    @model_validator(mode='after')
    def check_mutual_exclusion(self):
        if self.includes is not None and self.excludes is not None:
            raise ValueError("Cannot specify both 'includes' and 'excludes' in agents config")
        return self


class SkillRepoConfig(BaseModel):
    repo: str | None = None
    local_path: str | None = None
    skills: list[str] | None = None
    agents: AgentsConfig | None = None

    @model_validator(mode='after')
    def check_source(self):
        if self.repo and self.local_path:
            raise ValueError("Cannot specify both 'repo' and 'local_path'; exactly one must be set")
        if not self.repo and not self.local_path:
            raise ValueError("Must specify exactly one of 'repo' or 'local_path'")
        return self

    @property
    def is_local(self) -> bool:
        return self.local_path is not None

    @property
    def source_key(self) -> str:
        if self.local_path:
            return str(Path(self.local_path).expanduser())
        return self.repo


class DefaultAgentsConfig(BaseModel):
    default: list[str] | None = None

    @field_validator('default')
    @classmethod
    def check_known_agents(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            unknown = [a for a in v if a not in KNOWN_AGENTS]
            if unknown:
                raise ValueError(f'Unknown agents: {unknown}. Known agents: {list(KNOWN_AGENTS.keys())}')
        return v


class SkmConfig(BaseModel):
    packages: list[SkillRepoConfig]
    agents: DefaultAgentsConfig | None = None


AgentInstallMode = Literal['symlink', 'materialize']


class AgentSpec(BaseModel):
    path: str
    parent_env_var: str | None = None
    install_mode: AgentInstallMode = 'symlink'


class AgentSpecLoadError(RuntimeError):
    """Raised when bundled agent specs cannot be loaded."""


# --- Lock file models ---


class InstalledSkill(BaseModel):
    name: str
    repo: str | None = None
    local_path: str | None = None
    commit: str | None = None
    skill_path: str  # relative path within repo to the skill dir
    linked_to: list[str]  # list of managed install paths


class LockFile(BaseModel):
    skills: list[InstalledSkill] = []


# --- Runtime models ---


class DetectedSkill(BaseModel):
    """A skill detected by walking a cloned repo."""

    name: str  # from SKILL.md frontmatter
    path: Path  # absolute path to the skill directory
    relative_path: str  # relative path within the repo


# --- Constants ---

def _load_agent_specs() -> dict[str, AgentSpec]:
    try:
        raw_text = files('skm').joinpath('agent_specs.toml').read_text(encoding='utf-8')
    except FileNotFoundError as exc:
        raise AgentSpecLoadError(
            "Missing bundled agent_specs.toml. Reinstall skm or check your package build."
        ) from exc

    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        raise AgentSpecLoadError('Invalid bundled agent_specs.toml.') from exc

    raw_agents = data.get('agents')
    if not isinstance(raw_agents, dict):
        raise AgentSpecLoadError("Invalid bundled agent_specs.toml: missing [agents] table.")

    return {name: AgentSpec(**raw_spec) for name, raw_spec in raw_agents.items()}


AGENT_SPECS: dict[str, AgentSpec] = _load_agent_specs()


def _get_known_agents() -> dict[str, str]:
    """Return known agent paths, applying env-var overrides where set."""

    result: dict[str, str] = {}
    for agent, spec in AGENT_SPECS.items():
        if spec.parent_env_var:
            val = os.environ.get(spec.parent_env_var)
            if val:
                result[agent] = str(Path(val).expanduser() / 'skills')
                continue
        result[agent] = spec.path
    return result


KNOWN_AGENTS: dict[str, str] = _get_known_agents()


def get_agent_install_mode(agent_name: str) -> AgentInstallMode:
    spec = AGENT_SPECS.get(agent_name)
    if spec is None:
        return 'symlink'
    return spec.install_mode

CONFIG_DIR = Path('~/.config/skm').expanduser()
CONFIG_PATH = CONFIG_DIR / 'skills.yaml'
LOCK_PATH = CONFIG_DIR / 'skills-lock.yaml'
STORE_DIR = Path('~/.local/share/skm/skills').expanduser()
