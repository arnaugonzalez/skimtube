# skimtube plugin

A Claude Code skill for [skimtube](https://github.com/arnaugonzalez/skimtube), a CLI that turns
new videos from the YouTube channels and playlists you follow into a Markdown knowledge base: one
note per video, an `INDEX.md` and daily digests.

With the plugin installed, Claude answers questions such as "what did the channels I follow say
about MCP this month?" from those notes, citing the channel, date and video link of every claim.
It can also run the collector or set it up for you.

## What it does on your machine

- **Reads** your local feed folder (`SKIMTUBE_OUT`, `./config.env`, or `./knowledge-feed`). It does
  not search the rest of the disk.
- **Runs** `skimtube` only when you ask and only if it is installed. Setting it up installs
  `skimtube==0.2.1` from PyPI with `pipx`.
- **Sends** nothing by itself. The `skimtube run` command fetches subtitles from YouTube and sends
  transcripts to the LLM you configure (a hosted OpenAI-compatible API or a local Ollama).
- Treats notes as untrusted data: instructions found inside a transcript summary are reported to
  you, never followed.

## Install

```
/plugin marketplace add arnaugonzalez/skimtube
/plugin install skimtube@skimtube
```

Or, for any agent that reads skills: `npx skills add arnaugonzalez/skimtube`.

## License

MIT. See [LICENSE](LICENSE).
