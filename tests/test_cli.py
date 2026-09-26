import json
import re
import subprocess
import sys
from pathlib import Path

from skimtube import __version__
from skimtube.cli import main


def test_help_runs_as_module():
    r = subprocess.run([sys.executable, "-m", "skimtube.cli", "--help"],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0 and "knowledge base" in r.stdout


def test_init_creates_files_and_is_idempotent(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "init"]) == 0
    assert {p.name for p in tmp_path.iterdir()} == {"config.env", "channels.txt", "blocklist.txt"}
    (tmp_path / "channels.txt").write_text("@mine\n")
    assert main(["-C", str(tmp_path), "init"]) == 0
    assert (tmp_path / "channels.txt").read_text() == "@mine\n"
    assert "left as is" in capsys.readouterr().out


def test_run_after_init_explains_missing_model(tmp_path, capsys):
    main(["-C", str(tmp_path), "init"])
    assert main(["-C", str(tmp_path), "run"]) == 2
    assert "SKIMTUBE_LLM_MODEL" in capsys.readouterr().err


def test_digest_with_bad_config(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("SKIMTUBE_MAX_PER_RUN", "lots")
    assert main(["-C", str(tmp_path), "digest"]) == 2
    assert "SKIMTUBE_MAX_PER_RUN" in capsys.readouterr().err


def test_version_matches_pyproject():
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text()
    assert re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1) == __version__
    manifest = Path(__file__).parent.parent / "plugin/.claude-plugin/plugin.json"
    plugin = json.loads(manifest.read_text())
    assert plugin["version"] == __version__
