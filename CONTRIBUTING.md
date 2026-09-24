# Contributing

Bug reports and small PRs are welcome. For anything bigger, open an issue first.

```bash
uv sync            # or: python -m venv .venv && pip install -e . pytest ruff
uv run pytest      # offline: YouTube and the LLM are faked
uv run ruff check .
```

Rules of thumb: stdlib first (the only runtime dependency is `yt-dlp`), tests must not use the
network, and a new config key needs a line in `templates/config.env` and in the README table.
