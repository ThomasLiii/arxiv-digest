from datetime import date

from arxiv_digest import fetch, render
from arxiv_digest.triage import Score
from conftest import feed_bytes


def make_digest(scores):
    feeds = [fetch.parse_feed(feed_bytes(n)) for n in ("astro-ph.CO.xml", "astro-ph.IM.xml")]
    papers = fetch.merge(feeds, include_cross_lists=True, include_replacements=True).papers
    return render.Digest(
        date(2024, 4, 9), papers, {k: Score(*v) for k, v in scores.items()}, ["astro-ph.CO", "astro-ph.IM"]
    )


SCORES = {
    "2404.04321": ("high", 7, "Weak-lensing mass map of a merging cluster."),
    "2404.04491": ("high", 9, "ML shape recovery from survey imaging."),
    "2404.05140": ("medium", 5, "Calibration pipeline."),
    "2404.04801": ("low", 2, "Detector simulation."),
    "2404.04320": ("skip", 0, ""),
    "2404.04401": ("skip", 0, ""),
    "2307.07403": ("low", 1, "Revised constraints."),
}


def test_sections_are_ranked_and_complete():
    text = render.render(make_digest(SCORES))
    assert text.startswith("# arXiv digest — Tuesday 9 April 2024\n")
    assert "**2 high · 1 medium · 2 low** of 8 papers announced in astro-ph.CO, astro-ph.IM." in text
    high = text.index("## High priority")
    medium = text.index("## Medium priority")
    low = text.index("## Low priority")
    assert high < text.index("Galaxy 3D Shape") < text.index("Substructures within") < medium < low
    assert "**Why:** ML shape recovery from survey imaging." in text
    assert "[PDF](https://arxiv.org/pdf/2404.04491)" in text
    assert "`astro-ph.CO` (revised)" in text  # replacement
    assert "<details><summary>Skipped (2)</summary>" in text
    assert text.endswith("<sub>Ranked by Claude Code.</sub>\n")


def test_unscored_papers_are_listed():
    text = render.render(make_digest(SCORES))
    # 2312.04018 has no score: it must still appear.
    assert "## Not scored (1)" in text
    assert "https://arxiv.org/abs/2312.04018" in text


def test_empty_sections_and_skipped_toggle():
    text = render.render(make_digest({"2404.04320": ("skip", 0, "")}), list_skipped=False)
    assert text.count("_Nothing today._") == 3
    assert "Skipped" not in text


def test_titles_with_brackets_keep_links_intact():
    digest = make_digest(SCORES)
    digest.papers[0].title = "A [new] method"
    assert r"[A \[new\] method](https://arxiv.org/abs/2404.04321)" in render.render(digest)


def test_brief_has_only_high_and_medium():
    brief = render.render_brief(make_digest(SCORES))
    assert brief.startswith("**2 high · 1 medium · 2 low** of 8 papers.")
    assert "### High priority" in brief and "### Medium priority" in brief
    assert "Detector simulation" not in brief


def test_commit_message():
    assert make_digest(SCORES).commit_message() == "digest: 2024-04-09 (2 high · 1 medium · 2 low)"
