"""Configuration: defaults < config.env < environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULTS: dict[str, str] = {
    "YTC_OUT": "knowledge-feed",
    "YTC_CHANNELS": "channels.txt",
    "YTC_BLOCKLIST": "blocklist.txt",
    "YTC_STATE": "state.json",
    "YTC_SUB_LANGS": "en,en-orig,en-US",
    "YTC_LOOKBACK_HOURS": "24",
    "YTC_MAX_PER_RUN": "25",
    "YTC_MAX_TRANSCRIPT_CHARS": "48000",
    "YTC_KEYWORDS": "",
    "YTC_TOPIC": "technology and AI",
    "YTC_SUMMARY_LANG": "English",
    "YTC_LLM_PROVIDER": "openai",
    "YTC_LLM_BASE_URL": "https://api.openai.com/v1",
    "YTC_LLM_API_KEY": "",
    "YTC_LLM_MODEL": "",
    "YTC_LLM_COMMAND": "",
    "YTC_LLM_TIMEOUT": "300",
    "YTC_YTDLP_BIN": "yt-dlp",
}

INT_KEYS = ("YTC_MAX_PER_RUN", "YTC_MAX_TRANSCRIPT_CHARS", "YTC_LLM_TIMEOUT")
FLOAT_KEYS = ("YTC_LOOKBACK_HOURS",)
PROVIDERS = ("openai", "command")


class ConfigError(ValueError):
    """Invalid or incomplete configuration, with a message meant for the user."""


@dataclass
class Config:
    workdir: Path
    values: dict[str, str]

    def __getitem__(self, key: str) -> str:
        return self.values[key]

    def path(self, key: str) -> Path:
        p = Path(self.values[key]).expanduser()
        return p if p.is_absolute() else self.workdir / p

    def int(self, key: str) -> int:
        return int(self.values[key])

    def float(self, key: str) -> float:
        return float(self.values[key])

    def list(self, key: str) -> list[str]:
        return [x.strip() for x in self.values[key].split(",") if x.strip()]


def parse_env_file(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        out[key.strip().removeprefix("export ").strip()] = value
    return out


def config_file(workdir: Path) -> Path | None:
    local = workdir / "config.env"
    if local.exists():
        return local
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    user = xdg / "yt-collector" / "config.env"
    return user if user.exists() else None


def load(workdir: Path | None = None, env: dict[str, str] | None = None) -> Config:
    workdir = (workdir or Path.cwd()).resolve()
    env = dict(os.environ) if env is None else env
    values = dict(DEFAULTS)
    cfg_path = config_file(workdir)
    if cfg_path:
        values.update(parse_env_file(cfg_path.read_text(encoding="utf-8")))
    for key in DEFAULTS:
        if key in env:
            values[key] = env[key]
    if not values["YTC_LLM_API_KEY"] and env.get("OPENAI_API_KEY"):
        values["YTC_LLM_API_KEY"] = env["OPENAI_API_KEY"]

    for key in INT_KEYS:
        if not values[key].isdigit() or int(values[key]) == 0:
            raise ConfigError(f"{key} must be a positive integer, got {values[key]!r}")
    for key in FLOAT_KEYS:
        try:
            float(values[key])
        except ValueError:
            raise ConfigError(f"{key} must be a number, got {values[key]!r}") from None
    if values["YTC_LLM_PROVIDER"] not in PROVIDERS:
        raise ConfigError(
            f"YTC_LLM_PROVIDER must be one of {', '.join(PROVIDERS)}; "
            f"got {values['YTC_LLM_PROVIDER']!r}")
    return Config(workdir=workdir, values=values)


def check_llm(cfg: Config) -> None:
    """Fail before touching YouTube if the LLM settings cannot possibly work."""
    if cfg["YTC_LLM_PROVIDER"] == "command":
        if not cfg["YTC_LLM_COMMAND"]:
            raise ConfigError("YTC_LLM_PROVIDER=command needs YTC_LLM_COMMAND "
                              "(e.g. 'claude -p' or 'llm -m gpt-4o-mini')")
        return
    if not cfg["YTC_LLM_MODEL"]:
        raise ConfigError("Set YTC_LLM_MODEL (e.g. 'gpt-4o-mini', "
                          "'deepseek/deepseek-chat' on OpenRouter, 'llama3.1' on Ollama)")
    host = urlparse(cfg["YTC_LLM_BASE_URL"]).hostname or ""
    if not cfg["YTC_LLM_API_KEY"] and host not in ("localhost", "127.0.0.1", "::1"):
        raise ConfigError(f"Set YTC_LLM_API_KEY for {cfg['YTC_LLM_BASE_URL']} "
                          "(only local endpoints such as Ollama work without a key)")
