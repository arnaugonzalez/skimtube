import sys
from pathlib import Path

import pytest

from skimtube import config

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_LLM = f"{sys.executable} {FIXTURES / 'fake_llm.py'}"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """No real config, OAuth token or API key may leak into a test."""
    for key in list(config.DEFAULTS) + ["OPENAI_API_KEY", "SKIMTUBE_OAUTH_CLIENT_ID",
                                        "SKIMTUBE_OAUTH_CLIENT_SECRET"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


@pytest.fixture
def workdir(tmp_path):
    wd = tmp_path / "kb"
    wd.mkdir()
    (wd / "channels.txt").write_text("# comment\nUCAAAAAAAAAAAAAAAAAAAAAA\n")
    (wd / "config.env").write_text(
        "SKIMTUBE_LLM_PROVIDER=command\n"
        f"SKIMTUBE_LLM_COMMAND={FAKE_LLM}\n"
        "SKIMTUBE_LOOKBACK_HOURS=168\n")
    return wd
