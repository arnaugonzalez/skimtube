import sys
from pathlib import Path

import pytest

from yt_collector import config

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_LLM = f"{sys.executable} {FIXTURES / 'fake_llm.py'}"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """No real config, OAuth token or API key may leak into a test."""
    for key in list(config.DEFAULTS) + ["OPENAI_API_KEY", "YTC_OAUTH_CLIENT_ID",
                                        "YTC_OAUTH_CLIENT_SECRET"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


@pytest.fixture
def workdir(tmp_path):
    wd = tmp_path / "kb"
    wd.mkdir()
    (wd / "channels.txt").write_text("# comment\nUCAAAAAAAAAAAAAAAAAAAAAA\n")
    (wd / "config.env").write_text(
        "YTC_LLM_PROVIDER=command\n"
        f"YTC_LLM_COMMAND={FAKE_LLM}\n"
        "YTC_LOOKBACK_HOURS=168\n")
    return wd
