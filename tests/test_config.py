import pytest
from pathlib import Path
from skm.config import load_config


EXAMPLE_YAML = """\
packages:
  - repo: https://github.com/vercel-labs/agent-skills
    skills:
      - react-best-practices
      - web-design-guidelines
    agents:
      excludes:
        - openclaw
  - repo: https://github.com/blader/humanizer
"""

EXAMPLE_WITH_AGENTS_DEFAULT = """\
agents:
  default:
    - claude
    - standard

packages:
  - repo: https://github.com/vercel-labs/agent-skills
"""


def test_load_config(tmp_path):
    config_file = tmp_path / "skills.yaml"
    config_file.write_text(EXAMPLE_YAML)
    config = load_config(config_file)
    assert len(config.packages) == 2
    assert config.packages[0].repo == "https://github.com/vercel-labs/agent-skills"
    assert config.packages[0].skills == ["react-best-practices", "web-design-guidelines"]
    assert config.packages[0].agents.excludes == ["openclaw"]
    assert config.packages[1].repo == "https://github.com/blader/humanizer"
    assert config.packages[1].skills is None
    assert config.packages[1].agents is None
    assert config.agents is None


def test_load_config_with_agents_default(tmp_path):
    config_file = tmp_path / "skills.yaml"
    config_file.write_text(EXAMPLE_WITH_AGENTS_DEFAULT)
    config = load_config(config_file)
    assert config.agents is not None
    assert config.agents.default == ["claude", "standard"]
    assert len(config.packages) == 1


def test_load_config_unknown_agent(tmp_path):
    config_file = tmp_path / "skills.yaml"
    config_file.write_text("agents:\n  default:\n    - nonexistent\npackages:\n  - repo: https://example.com/repo\n")
    with pytest.raises(Exception, match="Unknown agents"):
        load_config(config_file)


def test_load_config_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_config_empty_file(tmp_path):
    config_file = tmp_path / "skills.yaml"
    config_file.write_text("")
    with pytest.raises(ValueError, match="empty"):
        load_config(config_file)
