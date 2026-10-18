# Changelog

## 0.2.1 — 2026-10-18

`skimtube add` on a long playlist no longer fails because of one bad video.

### Fixed
- `skimtube add` skips videos already in your knowledge base before fetching their metadata,
  so re-adding a playlist only asks YouTube about the new ones.
- A playlist video whose metadata fails (private, members-only, sign-in required, or a yt-dlp
  timeout) is logged and left out instead of aborting the whole playlist.

### Maintenance
- CI and release workflows move to `actions/checkout@v7`, `actions/setup-python@v7`,
  `astral-sh/setup-uv@v7`, `actions/upload-artifact@v7` and `actions/download-artifact@v8`
  (Node 24 runtime); ruff 0.16.9.
- Dependabot groups its updates into one PR for GitHub Actions and one for Python.

## 0.2.0 — 2026-10-10

Summarize a playlist, not just your channels, and survive YouTube's rate limits.

### Added
- `skimtube add URL... [-n N] [--force]` summarizes specific videos or whole playlists right
  away, outside the channel feed. A watch URL that carries `&list=` means its playlist; `-n 30`
  takes the first 30. Keyword and lookback filters do not apply: you picked these videos.
  Videos already in your knowledge base are skipped unless you pass `--force`.
- `SKIMTUBE_WORKERS` (default 1) summarizes, and lists playlists, that many videos at a time.
  With 4 workers and a CLI LLM, 30 videos took under 10 minutes.

### Fixed
- When YouTube refused subtitles (HTTP 429 or its bot check), the video was treated as having
  none and was never retried. It now stays pending for the next run, which exits 1 so a
  scheduler can tell. Upgrade if you run skimtube on a timer: a rate-limited window used to
  drop every new video it saw.

## 0.1.0 — 2026-09-26

First public release.

- `skimtube init | run | digest | auth` CLI.
- Any OpenAI-compatible LLM endpoint (OpenAI, OpenRouter, DeepSeek, Ollama, LM Studio…) or
  any CLI that reads a prompt on stdin (`SKIMTUBE_LLM_PROVIDER=command`).
- Per-video Markdown notes with YAML front matter, `INDEX.md`, and a digest with a
  contradictions section.
- LLM failures are retried on the next run (up to 3 times) instead of dropping the video.
- Claude Code plugin (`/plugin marketplace add arnaugonzalez/skimtube`) with a skill that
  answers from your notes and cites the videos.
- Security guidance for agent CLIs: transcripts are untrusted text, so run them with tools
  disabled (`claude -p --tools "" --strict-mcp-config`).
