import subprocess
import sys
from pathlib import Path


def test_built_wheel_can_load_packaged_agent_specs(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = tmp_path / 'dist'
    subprocess.run(
        ['uv', 'build', '--wheel', '--out-dir', str(dist_dir)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    wheels = list(dist_dir.glob('skm_cli-*.whl'))
    assert len(wheels) == 1
    wheel_path = wheels[0]

    script = """
import sys
from pathlib import Path

wheel = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(wheel))

import skm.types as types_mod

assert types_mod.AGENT_SPECS["claude"].parent_env_var == "CLAUDE_CONFIG_DIR"
assert types_mod.AGENT_SPECS["pi"].parent_env_var == "PI_CODING_AGENT_DIR"
print("ok")
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(wheel_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == 'ok'
