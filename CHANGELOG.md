# Changelog

## 0.1.0 — unreleased

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
