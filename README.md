# yt-collector

Turn the YouTube channels you never have time to watch into a searchable Markdown knowledge
base for you and your agents.

[![CI](https://github.com/arnaugonzalez/yt-collector/actions/workflows/ci.yml/badge.svg)](https://github.com/arnaugonzalez/yt-collector/actions/workflows/ci.yml)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

<!-- demo.gif: one generated note, then a digest with a contradictions section (≤20 s) -->

Every few hours it checks the channels you list, grabs the subtitles of new videos, and has an
LLM write one structured note per video. Once a day it merges the recent notes into a digest,
grouped by theme, with a section for **claims that contradict each other across sources**
("channel A says X, channel B says the opposite, same week").

```
knowledge-feed/
├── INDEX.md                      # one line per video, newest first
├── DIGEST.md                     # latest digest
├── digests/2026-09-21.md
└── 2026-09/
    └── 2026-09-20_some-channel_new-open-model-beats-gpt_abc123.md
```

## Quickstart

```bash
pipx install yt-collector                      # or: uv tool install yt-collector
mkdir kb && cd kb && yt-collector init         # writes config.env, channels.txt, blocklist.txt
YTC_LLM_API_KEY=sk-or-... YTC_LLM_MODEL=deepseek/deepseek-chat yt-collector run
```

`init` points to OpenRouter by default. For a fully local setup, use Ollama instead:

```bash
YTC_LLM_BASE_URL=http://localhost:11434/v1 YTC_LLM_MODEL=llama3.1 yt-collector run
```

The first run only looks back 24 hours (`YTC_LOOKBACK_HOURS`). After that, every run processes
whatever is new since the previous one. Then:

```bash
yt-collector digest                  # merge the last 30 h of notes
yt-collector digest --window-hours 168   # weekly
```

## Why not…

| | Watches channels unattended | Output | Contradictions between sources | Cost |
|---|---|---|---|---|
| **yt-collector** | yes (RSS, no API key) | one Markdown note per video + index + digest, in a folder | yes | your LLM (≈$0.002/note measured with DeepSeek; $0 with Ollama) |
| [fabric](https://github.com/danielmiessler/fabric) | no, one URL at a time | stdout | no | your LLM |
| [tubeless](https://github.com/seokhoonj/tubeless) | yes | daily ranked briefing, one file per day | no | your LLM |
| NotebookLM / Eightify / Glasp | no | in their app | no | free tier / subscription |
| Feedly Leo / Readwise Reader | feeds, not transcripts | in their app | no | subscription |

fabric has a much larger prompt library, and tubeless also transcribes videos without
subtitles (Whisper) and ranks them by importance. Pick them if you want a daily briefing to
read. Pick yt-collector if you want the notes to pile up as files that you, Obsidian or a coding
agent can `grep` months later.

## How it works

```mermaid
flowchart LR
  A[channels.txt<br/>+ optional subscriptions] --> B[YouTube RSS<br/>per channel]
  B --> C{new video?<br/>keyword filter}
  C --> D[yt-dlp subtitles]
  D --> E[LLM: structured note<br/>or SKIP if off-topic]
  E --> F[knowledge-feed/YYYY-MM/*.md<br/>+ INDEX.md]
  F --> G[digest: themes,<br/>contradictions, weak signals]
  S[(state.json)] <--> C
```

- **No YouTube API key.** Channel feeds come from the public RSS endpoint; `@handles` are
  resolved to channel ids once and cached in `state.json`.
- **Idempotent.** Processed video ids live in `state.json`, so running it twice does nothing
  new. If the LLM call fails, the video is retried on the next run (up to 3 times) and the run
  exits with status 1 so your scheduler shows the failure.
- **Notes have a fixed shape**: YAML front matter (`title`, `channel`, `url`, `video_id`,
  `published`, `collected`) and the sections *TL;DR, Key topics, What's new, Entities, Facts
  and figures*. Headings stay in English; the content follows `YTC_SUMMARY_LANG`.

## Configuration

Values come from `config.env` in the working directory (or `-C DIR`), else
`$XDG_CONFIG_HOME/yt-collector/config.env`. Environment variables override both.

| Variable | Default | |
|---|---|---|
| `YTC_LLM_BASE_URL` | `https://api.openai.com/v1` | any OpenAI-compatible endpoint |
| `YTC_LLM_API_KEY` | falls back to `OPENAI_API_KEY` | not needed for localhost |
| `YTC_LLM_MODEL` | — (required) | |
| `YTC_LLM_PROVIDER` | `openai` | `command` pipes the prompt into `YTC_LLM_COMMAND` (e.g. `claude -p`, `llm -m …`) |
| `YTC_SUMMARY_LANG` | `English` | language of the note content |
| `YTC_TOPIC` | `technology and AI` | the LLM skips off-topic videos; empty = keep all |
| `YTC_KEYWORDS` | empty | cheap whole-word pre-filter on title + description |
| `YTC_OUT` | `knowledge-feed` | |
| `YTC_CHANNELS` / `YTC_BLOCKLIST` / `YTC_STATE` | `channels.txt` / `blocklist.txt` / `state.json` | |
| `YTC_SUB_LANGS` | `en,en-orig,en-US` | subtitle languages, tried one at a time |
| `YTC_LOOKBACK_HOURS` | `24` | first run only |
| `YTC_MAX_PER_RUN` | `25` | the rest wait for the next run |
| `YTC_MAX_TRANSCRIPT_CHARS` | `48000` | transcript truncation |
| `YTC_YTDLP_BIN` | empty = the bundled yt-dlp | set to use another yt-dlp binary |

**Your subscriptions (optional).** `yt-collector auth` runs a one-time OAuth consent (read-only
scope) and from then on merges the channels you are subscribed to. It needs your own Google
Cloud OAuth client of type *Desktop app* (`YTC_OAUTH_CLIENT_ID` / `YTC_OAUTH_CLIENT_SECRET`).
While the OAuth app stays in "testing" mode, Google expires the refresh token after a while:
re-run `auth` when the log says so.

## Scheduling

`run` and `digest` are plain idempotent commands. See [`examples/`](examples/) for cron, a
systemd user timer, and a GitHub Actions workflow. To publish the feed somewhere else, chain
it: `yt-collector run && rsync -a knowledge-feed/ server:kb/`.

## Limits

- **Subtitles are required.** Videos without subtitles or auto-captions are skipped.
- **Datacenter IPs get bot-checked.** YouTube often refuses subtitle downloads from cloud
  servers ("Sign in to confirm you're not a bot"). A home machine works reliably; on a server
  you need yt-dlp cookies or a proxy.
- **Terms of service.** Downloading subtitles with yt-dlp is not a use YouTube explicitly
  permits. yt-collector keeps transcripts in memory only and writes transformed summaries.
  Don't redistribute transcripts, and check the rules that apply to you.
- The contradictions section is only as good as the model you use. Treat it as a pointer to
  check, not a verdict.

Non-goals: a web UI, a database, transcribing audio.

## License

MIT
