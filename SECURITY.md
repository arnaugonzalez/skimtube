# Security

Please report vulnerabilities privately through GitHub's
"Report a vulnerability" button (Security tab) rather than in a public issue.

Things worth knowing:

- API keys are read from environment variables or `config.env`; the key is only sent to
  `YTC_LLM_BASE_URL`. Keep `config.env` out of version control (it is in `.gitignore`).
- `YTC_LLM_PROVIDER=command` runs `YTC_LLM_COMMAND` with your user's permissions, and feeds it
  transcripts, which are untrusted text (prompt injection). If the command is an agent CLI, turn
  its tools off, e.g. `claude -p --tools "" --strict-mcp-config`; with tools on, a crafted video can make it run commands.
- yt-collector opens no ports, runs no shell (subprocesses get argument lists) and sends no
  telemetry. Output file names are slugified; front matter values are JSON-escaped.
- The optional OAuth refresh token lives at `$XDG_CONFIG_HOME/yt-collector/token.json`
  (mode 0600) with the read-only `youtube.readonly` scope.
- Transcripts are sent to the LLM provider you configure.
