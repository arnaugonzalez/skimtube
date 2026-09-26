"""LLM backends: any OpenAI-compatible endpoint, or any CLI that reads stdin."""
from __future__ import annotations

import json
import shlex
import subprocess
import time
import urllib.error
import urllib.request

from .config import Config

RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """The LLM call failed; the video should be retried on a later run."""


def complete(cfg: Config, system: str, user: str) -> str:
    if cfg["SKIMTUBE_LLM_PROVIDER"] == "command":
        return _command(cfg, system, user)
    return _openai(cfg, system, user)


def _openai(cfg: Config, system: str, user: str, attempts: int = 3) -> str:
    url = cfg["SKIMTUBE_LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": cfg["SKIMTUBE_LLM_MODEL"],
        "temperature": 0.2,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    headers = {"Content-Type": "application/json"}
    if cfg["SKIMTUBE_LLM_API_KEY"]:
        headers["Authorization"] = f"Bearer {cfg['SKIMTUBE_LLM_API_KEY']}"

    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=cfg.int("SKIMTUBE_LLM_TIMEOUT")) as r:
                data = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in RETRY_STATUS and attempt < attempts:
                time.sleep(2 ** attempt)
                continue
            raise LLMError(f"HTTP {e.code} from {url}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < attempts:
                time.sleep(2 ** attempt)
                continue
            raise LLMError(f"cannot reach {url}: {e}") from e
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"unexpected response shape from {url}: {str(data)[:300]}") from None
    if not content or not content.strip():
        raise LLMError(f"empty completion from {url}")
    return content.strip()


def _command(cfg: Config, system: str, user: str) -> str:
    cmd = shlex.split(cfg["SKIMTUBE_LLM_COMMAND"])
    try:
        r = subprocess.run(cmd, input=f"{system}\n\n---\n\n{user}", capture_output=True,
                           text=True, timeout=cfg.int("SKIMTUBE_LLM_TIMEOUT"), check=False)
    except FileNotFoundError as e:
        raise LLMError(f"LLM command not found: {cmd[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise LLMError(f"LLM command timed out after {e.timeout}s") from e
    if r.returncode != 0:
        raise LLMError(f"LLM command exited {r.returncode}: {r.stderr.strip()[:300]}")
    if not r.stdout.strip():
        raise LLMError("LLM command returned empty output")
    return r.stdout.strip()
