from datetime import datetime, timezone

from skimtube import collect, digest
from skimtube.config import load

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def make_note(out, vid, title, claim, collected=NOW):
    v = {"id": vid, "title": title, "author": "Chan", "desc": "",
         "published": "2026-09-20T10:00:00+00:00", "url": f"https://www.youtube.com/watch?v={vid}"}
    body = (f"## TL;DR\n- {claim}\n\n## What's new\n- **New models**: ExampleLM\n\n"
            "## Entities\n- ExampleLM\n")
    return collect.write_note(out, v, body, collected)


def test_digest_reports_contradictions(workdir):
    out = workdir / "knowledge-feed"
    make_note(out, "v1", "ExampleLM is open", "CLAIM-OPEN weights")
    make_note(out, "v2", "ExampleLM stays closed", "CLAIM-CLOSED weights")
    assert digest.run(load(workdir), window_hours=30, max_notes=10, now=NOW) == 0
    text = (out / "DIGEST.md").read_text()
    assert text.startswith("# Digest — 2026-09-21")
    assert "2 notes" in text
    assert "## Contradictions (A vs B)" in text and "**A** ([1])" in text
    assert (out / "digests" / "2026-09-21.md").read_text() == text


def test_digest_without_contradictions(workdir):
    out = workdir / "knowledge-feed"
    make_note(out, "v1", "ExampleLM is open", "CLAIM-OPEN weights")
    digest.run(load(workdir), window_hours=30, max_notes=10, now=NOW)
    assert "No contradictions detected" in (out / "DIGEST.md").read_text()


def test_previous_digests_and_foreign_files_are_not_reingested(workdir):
    out = workdir / "knowledge-feed"
    make_note(out, "v1", "ExampleLM is open", "CLAIM-OPEN weights")
    (out / "digests").mkdir()
    (out / "digests" / "2026-09-20.md").write_text("# Digest — 2026-09-20\n\nCLAIM-CLOSED\n")
    (out / "2026-09" / "handwritten.md").write_text("---\ntitle: mine\n---\nCLAIM-CLOSED\n")
    notes = digest.recent_notes(out, NOW.replace(day=20), NOW, 10)
    assert [n["url"] for n in notes] == ["https://www.youtube.com/watch?v=v1"]


def test_notes_from_the_old_name_are_still_read(workdir):
    out = workdir / "knowledge-feed"
    path = make_note(out, "v1", "legacy", "x")
    path.write_text(path.read_text().replace("source: skimtube", "source: yt-collector"))
    notes = digest.recent_notes(out, NOW.replace(day=20), NOW, 10)
    assert [n["title"] for n in notes] == ["legacy"]


def test_window_and_cap(workdir):
    out = workdir / "knowledge-feed"
    make_note(out, "old", "old", "x", collected=NOW.replace(day=1))
    for i in range(3):
        make_note(out, f"n{i}", f"note {i}", "x", collected=NOW.replace(hour=i))
    assert len(digest.recent_notes(out, NOW.replace(day=20), NOW, 10)) == 3
    assert len(digest.recent_notes(out, NOW.replace(day=20), NOW, 2)) == 2


def test_notes_after_now_are_excluded(workdir):
    out = workdir / "knowledge-feed"
    make_note(out, "v1", "before", "x", collected=NOW.replace(hour=1))
    make_note(out, "v2", "after", "x", collected=NOW.replace(day=22))
    notes = digest.recent_notes(out, NOW.replace(day=20), NOW, 10)
    assert [n["title"] for n in notes] == ["before"]


def test_empty_window_is_not_an_error(workdir):
    assert digest.run(load(workdir), window_hours=30, max_notes=10, now=NOW) == 0
    assert not (workdir / "knowledge-feed" / "DIGEST.md").exists()


def test_section_extraction():
    md = "## TL;DR\n- a\n\n## What's new\n- b\n## Entities\n- c"
    assert digest.section(md, "TL;DR") == "- a"
    assert digest.section(md, "What's new") == "- b"
    assert digest.section(md, "Missing") == ""
