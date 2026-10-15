"""YouTube access without an API key: channel pages, official RSS feeds, and yt-dlp subtitles."""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from . import log
from .config import Config

# Ids that belong to the page's own channel. A bare "channelId" is not one of them: a channel page
# also lists featured and recommended channels, and the first of those often comes first.
OWN_ID_RES = [
    re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[0-9A-Za-z_-]{22})"'),
    re.compile(r'"externalId"\s*:\s*"(UC[0-9A-Za-z_-]{22})"'),
    re.compile(r'<meta itemprop="identifier" content="(UC[0-9A-Za-z_-]{22})"'),
]
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) skimtube",
        "Accept-Language": "en",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def read_list(path: Path) -> list[str]:
    """Non-empty, non-comment lines of a channels/blocklist file."""
    if not path.exists():
        return []
    lines = (x.strip() for x in path.read_text(encoding="utf-8").splitlines())
    return [x for x in lines if x and not x.startswith("#")]


def resolve_channel(entry: str, cache: dict[str, str]) -> str | None:
    """Channel id (UC...) from a UC id, an @handle, a bare handle or a channel URL."""
    if re.fullmatch(r"UC[0-9A-Za-z_-]{22}", entry):
        return entry
    if entry in cache:
        return cache[entry]
    if entry.startswith("http"):
        url = entry
    else:
        url = f"https://www.youtube.com/@{entry.removeprefix('@')}"
    try:
        page = fetch(url)
    except OSError as e:
        log(f"warning: cannot resolve {entry!r}: {e}")
        return None
    cid = next((m.group(1) for r in OWN_ID_RES if (m := r.search(page))), None)
    if not cid:
        log(f"warning: no channel id found for {entry!r} (wrong handle?)")
        return None
    cache[entry] = cid
    log(f"resolved {entry} -> {cid}")
    return cid


def parse_feed(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    author = root.findtext("atom:title", default="", namespaces=NS)
    videos = []
    for e in root.findall("atom:entry", NS):
        vid = e.findtext("yt:videoId", default="", namespaces=NS)
        if not vid:
            continue
        group = e.find("media:group", NS)
        desc = "" if group is None else group.findtext("media:description", default="",
                                                         namespaces=NS)
        videos.append({
            "id": vid,
            "title": e.findtext("atom:title", default="", namespaces=NS),
            "published": e.findtext("atom:published", default="", namespaces=NS),
            "author": author,
            "desc": desc or "",
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    return videos


def channel_videos(channel_id: str) -> list[dict]:
    try:
        return parse_feed(fetch(FEED_URL.format(channel_id)))
    except OSError as e:
        log(f"warning: RSS failed for {channel_id}: {e}")
    except ET.ParseError as e:
        log(f"warning: malformed RSS for {channel_id}: {e}")
    return []


class YtDlpError(RuntimeError):
    """yt-dlp could not list a video or playlist."""


class BlockedError(RuntimeError):
    """YouTube refused the subtitles (HTTP 429 or bot check); the video may still have them."""


def _published(info: dict) -> str:
    """ISO timestamp from yt-dlp metadata: exact 'timestamp' if present, else 'upload_date'."""
    if info.get("timestamp"):
        return datetime.fromtimestamp(info["timestamp"], timezone.utc).isoformat()
    d = info.get("upload_date") or ""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}T00:00:00+00:00" if len(d) == 8 else ""


def _ytdlp_json(cfg: Config, args: list[str]) -> list[dict]:
    cmd = [*ytdlp_cmd(cfg), "--no-warnings", "--skip-download", "-J", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    if r.returncode != 0:
        raise YtDlpError(f"yt-dlp failed for {args[-1]}: {r.stderr.strip()[-300:]}")
    info = json.loads(r.stdout)
    return info.get("entries") or [info]


def list_videos(cfg: Config, url: str, limit: int | None = None,
                skip: set[str] | frozenset[str] = frozenset()) -> list[dict]:
    """Videos of a watch/playlist URL, in playlist order, with full metadata.

    A watch URL carrying '&list=' means the playlist, as on youtube.com. Ids in `skip` are
    dropped before fetching metadata; a video whose metadata fails (private, sign-in) is
    logged and left out instead of aborting the whole playlist."""
    if "list=" in url:
        url = "https://www.youtube.com/playlist?list=" + re.search(r"list=([\w-]+)", url).group(1)
    items = ["--flat-playlist"] + (["--playlist-items", f"1:{limit}"] if limit else [])
    entries = [e for e in _ytdlp_json(cfg, [*items, url])
               if e and e.get("id") and e["id"] not in skip]

    def full(e: dict) -> dict | None:
        if e.get("upload_date"):
            return e
        try:
            return _ytdlp_json(cfg, [f"https://www.youtube.com/watch?v={e['id']}"])[0]
        except YtDlpError as err:
            log(f"skip {e['id']}: {err}")
            return None

    with ThreadPoolExecutor(max_workers=max(1, cfg.int("SKIMTUBE_WORKERS"))) as pool:
        infos = [i for i in pool.map(full, entries) if i]
    return [{
        "id": info["id"],
        "title": info.get("title") or "",
        "published": _published(info),
        "author": info.get("channel") or info.get("uploader") or "",
        "desc": info.get("description") or "",
        "url": f"https://www.youtube.com/watch?v={info['id']}",
    } for info in infos]


def vtt_to_text(vtt: str) -> str:
    """Plain text from WebVTT, dropping timing, tags and the rolling duplicates of auto-subs."""
    lines, seen = [], set()
    for raw in vtt.lstrip("﻿").splitlines():
        s = raw.strip()
        if not s or s == "WEBVTT" or "-->" in s or re.fullmatch(r"\d+", s):
            continue
        if s.startswith(("Kind:", "Language:", "NOTE")):
            continue
        s = html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        if s and s not in seen:
            seen.add(s)
            lines.append(s)
    return " ".join(lines)


def ytdlp_cmd(cfg: Config) -> list[str]:
    """yt-dlp is a dependency, so by default run the copy installed next to this package:
    pipx/uv tool installs do not put dependency scripts on PATH."""
    if not cfg["SKIMTUBE_YTDLP_BIN"]:
        return [sys.executable, "-m", "yt_dlp"]
    found = shutil.which(cfg["SKIMTUBE_YTDLP_BIN"])
    if not found:
        raise FileNotFoundError(f"yt-dlp not found ({cfg['SKIMTUBE_YTDLP_BIN']!r}); "
                                "fix SKIMTUBE_YTDLP_BIN or leave it empty to use the bundled one")
    return [found]


def transcript(cfg: Config, video_url: str) -> str:
    """Subtitles tried one language at a time: requesting several at once lets a 429
    on an auto-translated track abort all of them."""
    base = ytdlp_cmd(cfg)
    cap = cfg.int("SKIMTUBE_MAX_TRANSCRIPT_CHARS")
    blocked = False
    for lang in cfg.list("SKIMTUBE_SUB_LANGS"):
        with tempfile.TemporaryDirectory() as td:
            cmd = [*base, "--skip-download", "--no-warnings",
                   "--write-subs", "--write-auto-subs", "--sub-langs", lang,
                   "--sub-format", "vtt", "--convert-subs", "vtt",
                   "--retries", "3", "--retry-sleep", "5",
                   "--sleep-requests", "1.5", "--socket-timeout", "30",
                   "-o", str(Path(td) / "sub"), video_url]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=240,
                                   check=False)
            except subprocess.TimeoutExpired:
                log(f"  yt-dlp timeout ({lang})")
                continue
            vtts = sorted(Path(td).glob("*.vtt"))
            if not vtts:
                if "429" in r.stderr:
                    blocked = True
                    log(f"  HTTP 429 on subtitles '{lang}', trying next language")
                elif "confirm you" in r.stderr:
                    blocked = True
                    log("  YouTube bot check: datacenter IPs are often blocked (see README)")
                continue
            text = vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="replace"))
            if len(text) >= 200:
                return text[:cap]
    if blocked:
        raise BlockedError(video_url)
    return ""
