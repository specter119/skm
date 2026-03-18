import skm.types as types_mod
import pytest

from skm.types import AgentSpecLoadError, AgentsConfig, SkillRepoConfig, get_agent_install_mode


def test_skill_repo_config_minimal():
    """Repo with no skills listed and no agents config."""
    cfg = SkillRepoConfig(repo="https://github.com/blader/humanizer")
    assert cfg.repo == "https://github.com/blader/humanizer"
    assert cfg.skills is None
    assert cfg.agents is None


def test_skill_repo_config_with_skills():
    cfg = SkillRepoConfig(
        repo="https://github.com/vercel-labs/agent-skills",
        skills=["react-best-practices", "react-native-skills"],
    )
    assert cfg.skills == ["react-best-practices", "react-native-skills"]


def test_agents_config_excludes():
    agents = AgentsConfig(excludes=["openclaw"])
    assert agents.excludes == ["openclaw"]
    assert agents.includes is None


def test_agents_config_includes():
    agents = AgentsConfig(includes=["claude", "codex"])
    assert agents.includes == ["claude", "codex"]
    assert agents.excludes is None


def test_skill_repo_config_with_agents():
    cfg = SkillRepoConfig(
        repo="https://github.com/vercel-labs/agent-skills",
        skills=["react-best-practices"],
        agents=AgentsConfig(excludes=["openclaw"]),
    )
    assert cfg.agents.excludes == ["openclaw"]


def test_get_known_agents_uses_parent_env_override(monkeypatch, tmp_path):
    home = tmp_path / 'home'
    claude_config_dir = home / '.claude-custom'

    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(claude_config_dir))

    agents = types_mod._get_known_agents()
    assert agents['claude'] == str(claude_config_dir / 'skills')


def test_load_agent_specs_from_toml():
    specs = types_mod._load_agent_specs()
    assert specs['standard'].install_mode == 'materialize'
    assert specs['claude'].parent_env_var == 'CLAUDE_CONFIG_DIR'
    assert specs['pi'].parent_env_var == 'PI_CODING_AGENT_DIR'


def test_load_agent_specs_raises_clear_error_when_resource_missing(monkeypatch):
    class _MissingResource:
        def joinpath(self, _name):
            return self

        def read_text(self, *, encoding):
            raise FileNotFoundError('missing')

    monkeypatch.setattr(types_mod, 'files', lambda _package: _MissingResource())

    with pytest.raises(AgentSpecLoadError, match='Missing bundled agent_specs.toml'):
        types_mod._load_agent_specs()


def test_load_agent_specs_raises_clear_error_for_invalid_toml(monkeypatch):
    class _InvalidResource:
        def joinpath(self, _name):
            return self

        def read_text(self, *, encoding):
            return 'not = [valid'

    monkeypatch.setattr(types_mod, 'files', lambda _package: _InvalidResource())

    with pytest.raises(AgentSpecLoadError, match='Invalid bundled agent_specs.toml'):
        types_mod._load_agent_specs()


def test_get_agent_install_mode_defaults_to_symlink():
    assert get_agent_install_mode('claude') == 'symlink'
    assert get_agent_install_mode('unknown-agent') == 'symlink'


def test_get_agent_install_mode_uses_materialize_for_standard_agents():
    assert get_agent_install_mode('standard') == 'materialize'
    assert get_agent_install_mode('openclaw') == 'materialize'
