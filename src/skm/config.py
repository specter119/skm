from pathlib import Path

import yaml

from skm.types import SkmConfig


def load_config(config_path: Path) -> SkmConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    text = config_path.read_text()
    data = yaml.safe_load(text)

    if not data:
        raise ValueError(f"Config file is empty: {config_path}")

    if not isinstance(data, dict):
        raise ValueError(
            f"Config must be a YAML dict with 'packages' key, got {type(data).__name__}: {config_path}"
        )

    return SkmConfig(**data)
