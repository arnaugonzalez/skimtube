# Changelog

## 0.1.0 — unreleased

First public release.

- `yt-collector init | run | digest | auth` CLI.
- Any OpenAI-compatible LLM endpoint (OpenAI, OpenRouter, DeepSeek, Ollama, LM Studio…) or
  any CLI that reads a prompt on stdin (`YTC_LLM_PROVIDER=command`).
- Per-video Markdown notes with YAML front matter, `INDEX.md`, and a digest with a
  contradictions section.
- LLM failures are retried on the next run (up to 3 times) instead of dropping the video.
