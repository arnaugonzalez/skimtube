"""`yt-collector digest`: merge recent notes by theme and surface contradictions between sources."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import llm, log, prompts
from .config import Config, check_llm

NOTE_DIR_RE = re.compile(r"^(\d{4}-\d{2}|undated)$")
CORPUS_CAP = 90_000


def section(md: str, header: str, limit: int = 1500) -> str:
    """Body of '## header' up to the next '## ' heading."""
    m = re.search(rf"^##\s+{re.escape(header)}[^\n]*\n(.*?)(?=^##\s|\Z)", md,
                  flags=re.MULTILINE | re.DOTALL)
    return m.group(1).strip()[:limit] if m else ""


def front_matter(md: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---", md, flags=re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm


def recent_notes(out: Path, since: datetime, until: datetime, cap: int) -> list[dict]:
    """Notes collected in [since, until], only from note folders (YYYY-MM / undated) and only
    files this tool wrote, so previous digests never feed back into a new one."""
    notes = []
    for folder in out.iterdir() if out.exists() else []:
        if not (folder.is_dir() and NOTE_DIR_RE.match(folder.name)):
            continue
        for path in folder.glob("*.md"):
            md = path.read_text(encoding="utf-8", errors="replace")
            fm = front_matter(md)
            if fm.get("source") != "yt-collector":
                continue
            try:
                dt = datetime.fromisoformat(fm.get("collected", "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if not since <= dt <= until:
                continue
            notes.append({
                "dt": dt,
                "title": fm.get("title", path.stem),
                "channel": fm.get("channel", "?"),
                "url": fm.get("url", ""),
                "tldr": section(md, "TL;DR"),
                "new": section(md, "What's new", 800),
                "entities": section(md, "Entities", 400),
            })
    notes.sort(key=lambda n: (n["dt"], n["url"]), reverse=True)
    return notes[:cap]


def build_corpus(notes: list[dict]) -> str:
    parts = []
    for i, n in enumerate(notes, 1):
        block = f"[{i}] {n['title']} — {n['channel']} ({n['url']})\nTL;DR: {n['tldr']}\n"
        if n["new"]:
            block += f"WHAT'S NEW: {n['new']}\n"
        if n["entities"]:
            block += f"ENTITIES: {n['entities']}\n"
        parts.append(block)
    return "\n".join(parts)[:CORPUS_CAP]


def run(cfg: Config, window_hours: float, max_notes: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    check_llm(cfg)
    out = cfg.path("YTC_OUT")
    notes = recent_notes(out, now - timedelta(hours=window_hours), now, max_notes)
    if not notes:
        log(f"digest: no notes in the last {window_hours:g}h, nothing to do")
        return 0
    log(f"digest: merging {len(notes)} note(s) from the last {window_hours:g}h")
    system = prompts.digest_system(cfg["YTC_SUMMARY_LANG"], cfg["YTC_TOPIC"])
    try:
        body = llm.complete(cfg, system, build_corpus(notes))
    except llm.LLMError as e:
        log(f"digest: LLM error: {e}")
        return 1
    day = now.date().isoformat()
    text = (f"# Digest — {day}\n\n"
            f"> Window: last {window_hours:g}h · {len(notes)} notes · "
            f"generated {now.isoformat(timespec='minutes')}\n\n{body}\n")
    ddir = out / "digests"
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / f"{day}.md").write_text(text, encoding="utf-8")
    (out / "DIGEST.md").write_text(text, encoding="utf-8")
    log(f"digest: wrote digests/{day}.md and DIGEST.md")
    return 0
