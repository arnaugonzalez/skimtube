"""Configuration: defaults < config.env < environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULTS: dict[str, str] = {
    "SKIMTUBE_OUT": "knowledge-feed",
    "SKIMTUBE_CHANNELS": "channels.txt",
    "SKIMTUBE_BLOCKLIST": "blocklist.txt",
    "SKIMTUBE_STATE": "state.json",
    "SKIMTUBE_SUB_LANGS": "en,en-orig,en-US",
    "SKIMTUBE_LOOKBACK_HOURS": "24",
    "SKIMTUBE_MAX_PER_RUN": "25",
    "SKIMTUBE_MAX_TRANSCRIPT_CHARS": "48000",
    "SKIMTUBE_KEYWORDS": "",
    "SKIMTUBE_TOPIC": "technology and AI",
    "SKIMTUBE_SUMMARY_LANG": "English",
    "SKIMTUBE_LLM_PROVIDER": "openai",
    "SKIMTUBE_LLM_BASE_URL": "https://api.openai.com/v1",
    "SKIMTUBE_LLM_API_KEY": "",
    "SKIMTUBE_LLM_MODEL": "",
    "SKIMTUBE_LLM_COMMAND": "",
    "SKIMTUBE_LLM_TIMEOUT": "300",
    "SKIMTUBE_YTDLP_BIN": "",
}

INT_KEYS = ("SKIMTUBE_MAX_PER_RUN", "SKIMTUBE_MAX_TRANSCRIPT_CHARS", "SKIMTUBE_LLM_TIMEOUT")
FLOAT_KEYS = ("SKIMTUBE_LOOKBACK_HOURS",)
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
    user = xdg / "skimtube" / "config.env"
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
    if not values["SKIMTUBE_LLM_API_KEY"] and env.get("OPENAI_API_KEY"):
        values["SKIMTUBE_LLM_API_KEY"] = env["OPENAI_API_KEY"]

    for key in INT_KEYS:
        if not values[key].isdigit() or int(values[key]) == 0:
            raise ConfigError(f"{key} must be a positive integer, got {values[key]!r}")
    for key in FLOAT_KEYS:
        try:
            float(values[key])
        except ValueError:
            raise ConfigError(f"{key} must be a number, got {values[key]!r}") from None
    if values["SKIMTUBE_LLM_PROVIDER"] not in PROVIDERS:
        raise ConfigError(
            f"SKIMTUBE_LLM_PROVIDER must be one of {', '.join(PROVIDERS)}; "
            f"got {values['SKIMTUBE_LLM_PROVIDER']!r}")
    return Config(workdir=workdir, values=values)


def check_llm(cfg: Config) -> None:
    """Fail before touching YouTube if the LLM settings cannot possibly work."""
    if cfg["SKIMTUBE_LLM_PROVIDER"] == "command":
        if not cfg["SKIMTUBE_LLM_COMMAND"]:
            raise ConfigError("SKIMTUBE_LLM_PROVIDER=command needs SKIMTUBE_LLM_COMMAND "
                              "(e.g. 'claude -p' or 'llm -m gpt-4o-mini')")
        return
    if not cfg["SKIMTUBE_LLM_MODEL"]:
        raise ConfigError("Set SKIMTUBE_LLM_MODEL (e.g. 'gpt-4o-mini', "
                          "'deepseek/deepseek-chat' on OpenRouter, 'llama3.1' on Ollama)")
    host = urlparse(cfg["SKIMTUBE_LLM_BASE_URL"]).hostname or ""
    if not cfg["SKIMTUBE_LLM_API_KEY"] and host not in ("localhost", "127.0.0.1", "::1"):
        raise ConfigError(f"Set SKIMTUBE_LLM_API_KEY for {cfg['SKIMTUBE_LLM_BASE_URL']} "
                          "(only local endpoints such as Ollama work without a key)")
