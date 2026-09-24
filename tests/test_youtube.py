from conftest import FIXTURES

from yt_collector import youtube


def test_parse_feed_fixture():
    videos = youtube.parse_feed((FIXTURES / "feed.xml").read_text())
    assert [v["id"] for v in videos] == ["vidAI000001", "vidCOOK0002", "vidOLD000003"]
    assert videos[0]["author"] == "Example Channel"
    assert videos[0]["url"] == "https://www.youtube.com/watch?v=vidAI000001"
    assert "agents" in videos[0]["desc"]


def test_vtt_to_text_strips_timing_tags_and_rolling_duplicates():
    text = youtube.vtt_to_text("﻿" + (FIXTURES / "sample.vtt").read_text())
    assert text == ("Today we look at a new open model that scores 71% on the "
                    "reasoning benchmark & runs locally.")


def test_vtt_to_text_empty():
    assert youtube.vtt_to_text("") == ""


def test_resolve_channel_id_passthrough_and_cache(monkeypatch):
    calls = []

    def fake_fetch(url, timeout=20):
        calls.append(url)
        return '..."channelId":"UCBBBBBBBBBBBBBBBBBBBBBB"...'

    monkeypatch.setattr(youtube, "fetch", fake_fetch)
    cache = {}
    assert youtube.resolve_channel("UCAAAAAAAAAAAAAAAAAAAAAA", cache) == "UCAAAAAAAAAAAAAAAAAAAAAA"
    assert youtube.resolve_channel("@someone", cache) == "UCBBBBBBBBBBBBBBBBBBBBBB"
    assert youtube.resolve_channel("@someone", cache) == "UCBBBBBBBBBBBBBBBBBBBBBB"
    assert calls == ["https://www.youtube.com/@someone"]


def test_resolve_channel_unknown_handle(monkeypatch):
    monkeypatch.setattr(youtube, "fetch", lambda url, timeout=20: "<html>nothing</html>")
    assert youtube.resolve_channel("nobody", {}) is None


def test_resolve_channel_network_error(monkeypatch):
    def boom(url, timeout=20):
        raise OSError("offline")

    monkeypatch.setattr(youtube, "fetch", boom)
    assert youtube.resolve_channel("@x", {}) is None
    assert youtube.channel_videos("UCAAAAAAAAAAAAAAAAAAAAAA") == []


def test_malformed_feed_returns_empty(monkeypatch):
    monkeypatch.setattr(youtube, "fetch", lambda url, timeout=20: "<feed><entry>")
    assert youtube.channel_videos("UCAAAAAAAAAAAAAAAAAAAAAA") == []


def test_read_list(tmp_path):
    f = tmp_path / "c.txt"
    f.write_text("# header\n\n  @a  \n#@b\nUCx\n")
    assert youtube.read_list(f) == ["@a", "UCx"]
    assert youtube.read_list(tmp_path / "missing.txt") == []
