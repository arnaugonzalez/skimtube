"""YouTube access without an API key: channel pages, official RSS feeds, and yt-dlp subtitles."""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

from . import log
from .config import Config

UC_RE = re.compile(r'"(?:channelId|externalId)"\s*:\s*"(UC[0-9A-Za-z_-]{22})"')
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) yt-collector",
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
    m = UC_RE.search(page)
    if not m:
        log(f"warning: no channel id found for {entry!r} (wrong handle?)")
        return None
    cache[entry] = m.group(1)
    log(f"resolved {entry} -> {m.group(1)}")
    return m.group(1)


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


def ytdlp_bin(cfg: Config) -> str:
    found = shutil.which(cfg["YTC_YTDLP_BIN"])
    if not found:
        raise FileNotFoundError(f"yt-dlp not found ({cfg['YTC_YTDLP_BIN']!r}); "
                                "install it or set YTC_YTDLP_BIN")
    return found


def transcript(cfg: Config, video_url: str) -> str:
    """Subtitles tried one language at a time: requesting several at once lets a 429
    on an auto-translated track abort all of them."""
    binary = ytdlp_bin(cfg)
    cap = cfg.int("YTC_MAX_TRANSCRIPT_CHARS")
    for lang in cfg.list("YTC_SUB_LANGS"):
        with tempfile.TemporaryDirectory() as td:
            cmd = [binary, "--skip-download", "--no-warnings",
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
                    log(f"  HTTP 429 on subtitles '{lang}', trying next language")
                elif "confirm you" in r.stderr:
                    log("  YouTube bot check: datacenter IPs are often blocked (see README)")
                continue
            text = vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="replace"))
            if len(text) >= 200:
                return text[:cap]
    return ""
