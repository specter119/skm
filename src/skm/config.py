from pathlib import Path

import yaml

from skm.types import SkillRepoConfig, SkmConfig


def load_config(config_path: Path) -> SkmConfig:
    if not config_path.exists():
        raise FileNotFoundError(f'Config file not found: {config_path}')

    text = config_path.read_text()
    data = yaml.safe_load(text)

    if not data:
        raise ValueError(f'Config file is empty: {config_path}')

    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML dict with 'packages' key, got {type(data).__name__}: {config_path}")

    return SkmConfig(**data)


def save_config(config: SkmConfig, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(exclude_none=True)
    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def upsert_package(config: SkmConfig, new_pkg: SkillRepoConfig) -> SkillRepoConfig | None:
    """Upsert a package into config. Returns existing package if found with skills: None, else None."""
    new_key = new_pkg.source_key

    for i, existing in enumerate(config.packages):
        if existing.source_key == new_key:
            # Found existing package
            if existing.skills is None:
                # Existing has all skills — return existing so caller can handle
                return existing

            if new_pkg.skills is not None:
                # Merge skills: union old + new, deduplicate
                merged = list(dict.fromkeys(existing.skills + new_pkg.skills))
                existing.skills = merged

            # Update agents config
            existing.agents = new_pkg.agents
            return None

    # Not found: append
    config.packages.append(new_pkg)
    return None
