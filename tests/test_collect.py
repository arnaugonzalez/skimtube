import json
from datetime import datetime, timezone

import pytest
from conftest import FIXTURES

from yt_collector import collect, youtube
from yt_collector.config import load

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
    assert "source: yt-collector\n---" in text
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
    cfg = load(workdir, env={"YTC_KEYWORDS": "llm, agents"})
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
    cfg = load(workdir, env={"YTC_MAX_PER_RUN": "1"})
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
