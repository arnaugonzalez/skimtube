import pytest

from yt_collector.config import ConfigError, check_llm, load, parse_env_file


def test_defaults_without_file(tmp_path):
    cfg = load(tmp_path, env={})
    assert cfg["YTC_LLM_PROVIDER"] == "openai"
    assert cfg.path("YTC_OUT") == tmp_path.resolve() / "knowledge-feed"
    assert cfg.list("YTC_KEYWORDS") == []


def test_file_then_env_precedence(tmp_path):
    (tmp_path / "config.env").write_text("YTC_MAX_PER_RUN=5   # inline comment\n"
                                         "export YTC_TOPIC='cooking'\n")
    cfg = load(tmp_path, env={"YTC_MAX_PER_RUN": "7"})
    assert cfg.int("YTC_MAX_PER_RUN") == 7
    assert cfg["YTC_TOPIC"] == "cooking"


def test_xdg_config_used_when_no_local_file(tmp_path, monkeypatch):
    xdg = tmp_path / "xdg" / "yt-collector"
    xdg.mkdir(parents=True)
    (xdg / "config.env").write_text("YTC_SUMMARY_LANG=Spanish\n")
    wd = tmp_path / "wd"
    wd.mkdir()
    assert load(wd, env={})["YTC_SUMMARY_LANG"] == "Spanish"


def test_absolute_paths_are_kept(tmp_path):
    cfg = load(tmp_path, env={"YTC_OUT": "/srv/feed"})
    assert str(cfg.path("YTC_OUT")) == "/srv/feed"


@pytest.mark.parametrize("key,value", [("YTC_MAX_PER_RUN", "ten"),
                                       ("YTC_LLM_TIMEOUT", "-1"),
                                       ("YTC_LOOKBACK_HOURS", "yesterday"),
                                       ("YTC_LLM_PROVIDER", "carrier-pigeon")])
def test_invalid_values_fail_with_the_key_name(tmp_path, key, value):
    with pytest.raises(ConfigError, match=key):
        load(tmp_path, env={key: value})


def test_check_llm_requires_model_and_remote_key(tmp_path):
    with pytest.raises(ConfigError, match="YTC_LLM_MODEL"):
        check_llm(load(tmp_path, env={}))
    with pytest.raises(ConfigError, match="YTC_LLM_API_KEY"):
        check_llm(load(tmp_path, env={"YTC_LLM_MODEL": "m"}))
    check_llm(load(tmp_path, env={"YTC_LLM_MODEL": "m", "OPENAI_API_KEY": "k"}))


def test_local_endpoint_needs_no_key(tmp_path):
    check_llm(load(tmp_path, env={"YTC_LLM_MODEL": "llama3.1",
                                  "YTC_LLM_BASE_URL": "http://localhost:11434/v1"}))


def test_command_provider_needs_command(tmp_path):
    with pytest.raises(ConfigError, match="YTC_LLM_COMMAND"):
        check_llm(load(tmp_path, env={"YTC_LLM_PROVIDER": "command"}))


def test_parse_env_file_ignores_noise():
    assert parse_env_file("\n# x\nnot a pair\nA=1\nB=\"two words\"\n") == {
        "A": "1", "B": "two words"}
