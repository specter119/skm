import subprocess

import click
import pytest
from skm.git import clone_or_pull, get_head_commit, repo_url_to_dirname


def test_repo_url_to_dirname():
    assert repo_url_to_dirname("https://github.com/vercel-labs/agent-skills") == "github.com_vercel-labs_agent-skills"
    assert repo_url_to_dirname("http://github.com/better-auth/skills") == "github.com_better-auth_skills"


def test_clone_and_get_commit(tmp_path):
    """Create a local git repo, clone it, and check commit."""
    # Set up a source repo
    src = tmp_path / "source"
    src.mkdir()
    subprocess.run(["git", "init"], cwd=src, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=src, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=src, capture_output=True)
    (src / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=src, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=src, capture_output=True)

    # Clone it
    dest = tmp_path / "dest"
    clone_or_pull(str(src), dest)
    assert (dest / "README.md").exists()

    commit = get_head_commit(dest)
    assert len(commit) == 40  # full SHA

    # Pull again (should not error)
    clone_or_pull(str(src), dest)


LS_TREE_OUTPUT = "100644 blob abc\tskills/a/SKILL.md\x00100644 blob def\tREADME.md\x00"


def _fake_run_cmd(calls):
    def fake(cmd, **kwargs):
        calls.append((cmd, kwargs))
        stdout = LS_TREE_OUTPUT if cmd[:3] == ["git", "ls-tree", "-r"] else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout)

    return fake


def test_clone_uses_partial_sparse_clone_by_default(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("skm.git.run_cmd", _fake_run_cmd(calls))

    dest = tmp_path / "store" / "repo"
    clone_or_pull("https://github.com/example/repo", dest)

    assert [c[0] for c in calls] == [
        ["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/example/repo", str(dest)],
        ["git", "ls-tree", "-r", "-z", "HEAD"],
        ["git", "sparse-checkout", "set", "--cone", "skills/a"],
        ["git", "checkout"],
    ]
    assert all(c[1].get("cwd") == dest for c in calls[1:])


def test_clone_uses_depth_for_shallow_strategy(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("skm.git.run_cmd", _fake_run_cmd(calls))

    dest = tmp_path / "store" / "repo"
    clone_or_pull("https://github.com/example/repo", dest, clone_strategy="shallow")

    assert calls[0][0] == [
        "git", "clone", "--filter=blob:none", "--depth", "1", "--no-checkout",
        "https://github.com/example/repo", str(dest),
    ]


def test_clone_disables_sparse_for_root_singleton(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("skm.git.run_cmd", _fake_run_cmd(calls))
    monkeypatch.setattr("skm.git.list_tree_files", lambda repo_path: ["SKILL.md", "docs/x.md"])

    dest = tmp_path / "store" / "repo"
    clone_or_pull("https://github.com/example/repo", dest)

    assert [c[0] for c in calls][1:] == [
        ["git", "sparse-checkout", "disable"],
        ["git", "checkout"],
    ]


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=path, capture_output=True, check=True)


def _commit_all(path, msg="commit"):
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=path, capture_output=True, check=True)


def _write(path, content="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _skill_md(name):
    return f"---\nname: {name}\ndescription: test\n---\n"


def test_sparse_clone_checks_out_only_skill_dirs(tmp_path):
    src = tmp_path / "source"
    _init_repo(src)
    _write(src / "skills" / "a" / "SKILL.md", _skill_md("a"))
    _write(src / "skills" / "b" / "SKILL.md", _skill_md("b"))
    _write(src / "skills" / "b" / "ref.md")
    _write(src / "big" / "blob.bin", "0" * 100000)
    _write(src / "README.md")
    _commit_all(src)

    dest = tmp_path / "dest"
    clone_or_pull(str(src), dest)

    assert (dest / "skills" / "a" / "SKILL.md").exists()
    assert (dest / "skills" / "b" / "ref.md").exists()
    assert not (dest / "big").exists()
    listed = subprocess.run(
        ["git", "sparse-checkout", "list"], cwd=dest, capture_output=True, text=True, check=True
    ).stdout.split()
    assert listed == ["skills/a", "skills/b"]


def test_sparse_clone_picks_up_new_skill_after_pull(tmp_path):
    src = tmp_path / "source"
    _init_repo(src)
    _write(src / "skills" / "a" / "SKILL.md", _skill_md("a"))
    _write(src / "big" / "blob.bin", "0" * 1000)
    _commit_all(src)

    dest = tmp_path / "dest"
    clone_or_pull(str(src), dest)
    assert not (dest / "skills" / "c").exists()

    _write(src / "skills" / "c" / "SKILL.md", _skill_md("c"))
    _commit_all(src, "add c")

    clone_or_pull(str(src), dest)
    assert (dest / "skills" / "c" / "SKILL.md").exists()
    assert not (dest / "big").exists()
    assert get_head_commit(dest) == subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_sparse_clone_root_singleton_does_full_checkout(tmp_path):
    src = tmp_path / "source"
    _init_repo(src)
    _write(src / "SKILL.md", _skill_md("root"))
    _write(src / "docs" / "x.md")
    _commit_all(src)

    dest = tmp_path / "dest"
    clone_or_pull(str(src), dest)
    assert (dest / "SKILL.md").exists()
    assert (dest / "docs" / "x.md").exists()


def test_sparse_clone_respects_skills_dir(tmp_path):
    src = tmp_path / "source"
    _init_repo(src)
    _write(src / "pkg" / "a" / "SKILL.md", _skill_md("a"))
    _write(src / "skills" / "b" / "SKILL.md", _skill_md("b"))
    _commit_all(src)

    dest = tmp_path / "dest"
    clone_or_pull(str(src), dest, skills_dir="pkg")
    assert (dest / "pkg" / "a" / "SKILL.md").exists()
    assert not (dest / "skills").exists()


def test_existing_full_clone_shrinks_on_pull(tmp_path):
    src = tmp_path / "source"
    _init_repo(src)
    _write(src / "skills" / "a" / "SKILL.md", _skill_md("a"))
    _write(src / "big" / "blob.bin", "0" * 1000)
    _commit_all(src)

    dest = tmp_path / "dest"
    subprocess.run(["git", "clone", "-q", str(src), str(dest)], capture_output=True, check=True)
    assert (dest / "big").exists()

    clone_or_pull(str(src), dest)
    assert (dest / "skills" / "a" / "SKILL.md").exists()
    assert not (dest / "big").exists()


@pytest.mark.network
def test_clone_real_repo(tmp_path):
    """Clone a real GitHub repo successfully."""
    dest = tmp_path / "firecrawl-cli"
    clone_or_pull("https://github.com/firecrawl/cli", dest)
    assert (dest / ".git").exists()

    commit = get_head_commit(dest)
    assert len(commit) == 40


@pytest.mark.network
def test_clone_nonexistent_repo(tmp_path):
    """Cloning a non-existent repo raises click.ClickException with stderr info."""
    dest = tmp_path / "bad-clone"
    with pytest.raises(click.ClickException) as exc_info:
        clone_or_pull("https://github.com/this-org-does-not-exist-skm-test/nonexistent-repo-xyz", dest)
    assert "stderr:" in exc_info.value.message
