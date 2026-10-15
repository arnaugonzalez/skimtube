import json
from datetime import datetime, timezone

import pytest
from conftest import FIXTURES

from skimtube import collect, youtube
from skimtube.config import load

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
TRANSCRIPT = "a long transcript about a new open model and its benchmark results " * 10


@pytest.fixture
def offline(monkeypatch):
    """Feed from the fixture; transcripts from a dict that tests can edit."""
    transcripts = {}
    monkeypatch.setattr(youtube, "fetch", lambda url, timeout=20:
                        (FIXTURES / "feed.xml").read_text())
    monkeypatch.setattr(youtube, "transcript", lambda cfg, url:
                        transcripts.get(url.rsplit("=", 1)[1], TRANSCRIPT))
    return transcripts


def notes(out):
    return sorted(p.name for p in out.glob("20*/*.md"))


def test_first_run_writes_note_with_front_matter(workdir, offline):
    cfg = load(workdir)
    assert collect.run(cfg, now=NOW) == 0
    out = workdir / "knowledge-feed"
    assert notes(out) == [
        "2026-09-20_example-channel_new-open-llm-beats-gpt-on-reasoning_vidAI000001.md"]
    text = (out / "2026-09" / notes(out)[0]).read_text()
    assert text.startswith('---\ntitle: "New open LLM beats GPT on reasoning"\n')
    assert "video_id: vidAI000001\n" in text
    assert "collected: 2026-09-21T12:00:00+00:00\n" in text
    assert "source: skimtube\n---" in text
    assert "## TL;DR" in text
    index = (out / "INDEX.md").read_text()
    assert index.count("vidAI000001") == 2  # note link + video link
    state = json.loads((workdir / "state.json").read_text())
    # AI video summarized, cooking video judged off-topic, old video outside lookback
    assert set(state["seen"]) == {"vidAI000001", "vidCOOK0002", "vidOLD000003"}


def test_second_run_is_idempotent(workdir, offline):
    cfg = load(workdir)
    collect.run(cfg, now=NOW)
    out = workdir / "knowledge-feed"
    before = ((out / "INDEX.md").read_text(), notes(out))
    assert collect.run(cfg, now=NOW) == 0
    assert ((out / "INDEX.md").read_text(), notes(out)) == before


def test_keyword_prefilter_skips_llm(workdir, offline, monkeypatch):
    calls = []
    real = collect.llm.complete
    monkeypatch.setattr(collect.llm, "complete",
                        lambda cfg, s, u: calls.append(u) or real(cfg, s, u))
    cfg = load(workdir, env={"SKIMTUBE_KEYWORDS": "llm, agents"})
    collect.run(cfg, now=NOW)
    assert len(calls) == 1 and "New open LLM" in calls[0]


def test_llm_failure_keeps_video_for_retry_then_gives_up(workdir, offline):
    offline["vidAI000001"] = "FAIL " + TRANSCRIPT
    cfg = load(workdir)
    for attempt in (1, 2):
        assert collect.run(cfg, now=NOW) == 1
        state = json.loads((workdir / "state.json").read_text())
        assert "vidAI000001" not in state["seen"]
        assert state["failures"] == {"vidAI000001": attempt}
    assert collect.run(cfg, now=NOW) == 1
    state = json.loads((workdir / "state.json").read_text())
    assert "vidAI000001" in state["seen"] and state["failures"] == {}


def test_recovers_after_transient_failure(workdir, offline):
    offline["vidAI000001"] = "FAIL " + TRANSCRIPT
    cfg = load(workdir)
    collect.run(cfg, now=NOW)
    del offline["vidAI000001"]
    assert collect.run(cfg, now=NOW) == 0
    assert len(notes(workdir / "knowledge-feed")) == 1


def test_short_transcript_is_skipped(workdir, offline):
    offline["vidAI000001"] = "too short"
    collect.run(load(workdir), now=NOW)
    assert notes(workdir / "knowledge-feed") == []


def test_blocklist(workdir, offline):
    (workdir / "blocklist.txt").write_text("UCAAAAAAAAAAAAAAAAAAAAAA\n")
    collect.run(load(workdir), now=NOW)
    assert not (workdir / "knowledge-feed").exists()


def test_max_per_run_keeps_the_rest_for_later(workdir, offline):
    cfg = load(workdir, env={"SKIMTUBE_MAX_PER_RUN": "1"})
    collect.run(cfg, now=NOW)
    state = json.loads((workdir / "state.json").read_text())
    assert "vidCOOK0002" not in state["seen"]  # older candidate deferred, not dropped


def test_corrupt_state_fails_loudly(workdir, offline):
    (workdir / "state.json").write_text("{not json")
    with pytest.raises(collect.StateError, match="state.json"):
        collect.run(load(workdir), now=NOW)


def test_no_channels(workdir, offline):
    (workdir / "channels.txt").write_text("# nothing yet\n")
    assert collect.run(load(workdir), now=NOW) == 1


@pytest.mark.parametrize("keywords,title,expected", [
    ([], "anything", True),
    (["ai"], "The AI news", True),
    (["ai"], "Rain in Spain, check your email", False),
    (["ia"], "Inteligencia artificial: la IA en 2026", True),
    (["ia"], "Mediación familiar", False),
    (["open-source"], "Why open-source models win", True),
    (["c++"], "Modern C++ tips", True),
    (["llm"], "LLMs", False),
])
def test_matches_keywords(keywords, title, expected):
    assert collect.matches_keywords({"title": title, "desc": ""}, keywords) is expected


def test_slugify_unicode_and_empty():
    assert collect.slugify("Café: ¿Qué es un LLM?") == "café-qué-es-un-llm"
    assert collect.slugify("!!!") == "video"


def test_index_is_rebuilt_under_header_when_missing_header(tmp_path):
    out = tmp_path
    (out / "INDEX.md").write_text("- old line\n")
    v = {"published": "2026-09-20T00:00:00+00:00", "author": "A", "title": "T",
         "url": "https://y/watch?v=1"}
    collect.update_index(out, [(v, out / "2026-09" / "n.md")])
    lines = (out / "INDEX.md").read_text().splitlines()
    assert lines[:4] == collect.INDEX_HEADER
    assert "[T](2026-09/n.md)" in lines[4] and lines[5] == "- old line"


@pytest.fixture
def listed(monkeypatch):
    videos = [{"id": f"vid{i}", "title": f"Video {i}", "published": "2026-09-20T10:00:00+00:00",
               "author": "Some Channel", "desc": "", "url": f"https://www.youtube.com/watch?v=vid{i}"}
              for i in range(3)]
    monkeypatch.setattr(youtube, "list_videos", lambda cfg, url, limit=None, skip=frozenset():
                        [v for v in videos[:limit] if v["id"] not in skip])
    return videos


def test_add_ignores_keywords_and_skips_seen(workdir, offline, listed):
    (workdir / "config.env").write_text((workdir / "config.env").read_text()
                                        + "SKIMTUBE_KEYWORDS=nothing-matches\n")
    cfg = load(workdir)
    assert collect.add(cfg, ["https://www.youtube.com/playlist?list=PLx"], limit=2, now=NOW) == 0
    assert len(notes(workdir / "knowledge-feed")) == 2
    assert collect.add(cfg, ["https://www.youtube.com/playlist?list=PLx"], now=NOW) == 0
    assert len(notes(workdir / "knowledge-feed")) == 3
    state = json.loads((workdir / "state.json").read_text())
    assert {"vid0", "vid1", "vid2"} <= set(state["seen"])


def test_add_force_rewrites_seen(workdir, offline, listed):
    cfg = load(workdir)
    collect.add(cfg, ["u"], now=NOW)
    (workdir / "knowledge-feed" / "INDEX.md").unlink()
    collect.add(cfg, ["u"], force=True, now=NOW)
    index = (workdir / "knowledge-feed" / "INDEX.md").read_text()
    assert sum(line.startswith("- ") for line in index.splitlines()) == 3


def test_parallel_workers_give_same_notes(workdir, offline):
    (workdir / "config.env").write_text((workdir / "config.env").read_text()
                                        + "SKIMTUBE_WORKERS=4\n")
    assert collect.run(load(workdir), now=NOW) == 0
    serial = workdir.parent / "serial"
    serial.mkdir()
    for f in ("channels.txt", "config.env"):
        (serial / f).write_text((workdir / f).read_text().replace("SKIMTUBE_WORKERS=4\n", ""))
    assert collect.run(load(serial), now=NOW) == 0
    assert notes(workdir / "knowledge-feed") == notes(serial / "knowledge-feed")


def test_blocked_subtitles_are_retried_not_marked_seen(workdir, monkeypatch, listed):
    def blocked(cfg, url):
        raise youtube.BlockedError(url)

    monkeypatch.setattr(youtube, "transcript", blocked)
    assert collect.add(load(workdir), ["u"], now=NOW) == 1
    assert json.loads((workdir / "state.json").read_text())["seen"] == []
