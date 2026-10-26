import json
from pathlib import Path

import pytest

from arxiv_digest import cli, fetch
from conftest import feed_bytes


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A digest repo in tmp_path with arXiv faked out; 6 papers in batches of 4."""
    (tmp_path / "interests.md").write_text("## High priority\n- weak lensing\n")
    (tmp_path / "digest.toml").write_text('categories = ["astro-ph.CO", "astro-ph.IM"]\nbatch_size = 4\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch, "fetch_feed", lambda category: feed_bytes(f"{category}.xml"))
    return tmp_path


def write_scores(work: Path, skip: set[str] = frozenset()):
    """Score every paper in each batch the way the session would, leaving out `skip`."""
    state = json.loads((work / "announcement.json").read_text())
    for n, ids in enumerate(state["batches"], 1):
        entries = [
            {"id": i, "priority": "high" if i == "2404.04321" else "skip", "score": 8, "reason": "Weak lensing."}
            for i in ids
            if i not in skip
        ]
        (work / f"scores-{n:02}.json").write_text(json.dumps({"papers": entries}))


def test_prepare_writes_instructions_and_batches(repo, capsys):
    assert cli.main(["prepare"]) == 0
    assert "Ready: 6 papers from 2024-04-09 in 2 batch files" in capsys.readouterr().out
    work = repo / ".digest"
    assert sorted(p.name for p in work.iterdir()) == ["INSTRUCTIONS.md", "announcement.json", "batch-01.md", "batch-02.md"]
    instructions = (work / "INSTRUCTIONS.md").read_text()
    assert "- weak lensing" in instructions
    assert "6 papers in 2 files, `.digest/batch-01.md` to `.digest/batch-02.md`" in instructions
    assert "python -m arxiv_digest finish" in instructions
    assert (work / "batch-02.md").read_text().count("<paper ") == 2


def test_finish_writes_digest_and_cleans_up(repo, capsys):
    cli.main(["prepare"])
    write_scores(repo / ".digest")
    capsys.readouterr()
    assert cli.main(["finish"]) == 0
    out = capsys.readouterr().out
    digest = (repo / "digests" / "2024-04-09.md").read_text()
    assert "**1 high · 0 medium · 0 low** of 6 papers" in digest
    assert digest.endswith("<sub>Ranked by Claude Code.</sub>\n")
    assert not (repo / ".digest").exists()
    assert "Digest: digests/2024-04-09.md" in out
    assert "Commit message: digest: 2024-04-09 (1 high · 0 medium · 0 low)" in out
    assert "### High priority" in out  # the brief, for the end of the session


def test_finish_lists_missing_scores(repo, capsys):
    cli.main(["prepare"])
    write_scores(repo / ".digest", skip={"2404.04801"})
    capsys.readouterr()
    assert cli.main(["finish"]) == 2
    assert "scores-02.json: 2404.04801" in capsys.readouterr().out
    assert not (repo / "digests").exists()
    assert (repo / ".digest").exists()

    assert cli.main(["finish", "--allow-missing"]) == 0
    assert "## Not scored (1)" in (repo / "digests" / "2024-04-09.md").read_text()


def test_finish_reports_bad_json(repo, capsys):
    cli.main(["prepare"])
    (repo / ".digest" / "scores-01.json").write_text('{"papers": [')
    assert cli.main(["finish"]) == 1
    assert "scores-01.json is not valid JSON" in capsys.readouterr().err


def test_finish_before_prepare(repo, capsys):
    assert cli.main(["finish"]) == 1
    assert "Run `python -m arxiv_digest prepare` first" in capsys.readouterr().err


def test_prepare_does_nothing_when_digest_exists(repo, capsys):
    (repo / "digests").mkdir()
    (repo / "digests" / "2024-04-09.md").write_text("done")
    assert cli.main(["prepare"]) == 0
    assert capsys.readouterr().out.startswith("Nothing to do: digests/2024-04-09.md already exists")
    assert not (repo / ".digest").exists()
    assert cli.main(["prepare", "--force"]) == 0
    assert (repo / ".digest" / "INSTRUCTIONS.md").exists()


def test_prepare_does_nothing_without_announcement(repo, monkeypatch, capsys):
    monkeypatch.setattr(fetch, "fetch_feed", lambda category: feed_bytes("empty.xml"))
    assert cli.main(["prepare"]) == 0
    assert capsys.readouterr().out.startswith("Nothing to do: no arXiv announcement")


def test_config_errors_are_one_line(repo, capsys):
    (repo / "digest.toml").write_text('categories = ["astro-ph.CO"]\nmodle = "x"\n')
    assert cli.main(["prepare"]) == 1
    assert capsys.readouterr().err.strip().endswith("unknown setting 'modle'")

