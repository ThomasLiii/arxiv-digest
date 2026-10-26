import io
import subprocess
import urllib.error
from datetime import date

import pytest

from arxiv_digest import fetch
from conftest import feed_bytes


def ids(announcement):
    return [p.id for p in announcement.papers]


def test_parse_feed():
    feed = fetch.parse_feed(feed_bytes("astro-ph.IM.xml"))
    assert feed.date == date(2024, 4, 9)
    assert len(feed.papers) == 5
    paper = feed.papers[0]
    assert paper.id == "2404.04491"
    assert paper.title.startswith("Galaxy 3D Shape Recovery using Mixture Density Net")
    assert "  " not in paper.title
    assert paper.announce_type == "new"
    assert paper.primary_category == "astro-ph.IM"
    assert len(paper.authors) == 6
    assert not paper.abstract.startswith(("arXiv:", "Abstract:"))
    assert paper.url == "https://arxiv.org/abs/2404.04491"


def test_parse_feed_keeps_long_author_lists():
    feed = fetch.parse_feed(feed_bytes("astro-ph.IM.xml"))
    big = next(p for p in feed.papers if p.id == "2404.04801")
    assert len(big.authors) == 279


def test_empty_feed_means_no_announcement():
    feed = fetch.parse_feed(feed_bytes("empty.xml"))
    assert feed.papers == []
    merged = fetch.merge([feed], include_cross_lists=True, include_replacements=False)
    assert merged.date is None


def test_merge_dedupes_and_prefers_new_listing():
    feeds = [fetch.parse_feed(feed_bytes(n)) for n in ("astro-ph.CO.xml", "astro-ph.IM.xml")]
    merged = fetch.merge(feeds, include_cross_lists=True, include_replacements=False)
    # 2404.05140 is a cross-list in CO but new in IM: it appears once, as new.
    assert ids(merged).count("2404.05140") == 1
    assert next(p for p in merged.papers if p.id == "2404.05140").announce_type == "new"
    assert ids(merged) == ["2404.04321", "2404.04320", "2404.05140", "2404.04491", "2404.04801", "2404.04401"]
    assert merged.date == date(2024, 4, 9)


def test_merge_filters_listing_types():
    feeds = [fetch.parse_feed(feed_bytes(n)) for n in ("astro-ph.CO.xml", "astro-ph.IM.xml")]

    no_cross = fetch.merge(feeds, include_cross_lists=False, include_replacements=False)
    assert {p.announce_type for p in no_cross.papers} == {"new"}
    assert "2404.05140" in ids(no_cross)

    with_replacements = fetch.merge(feeds, include_cross_lists=True, include_replacements=True)
    assert {"2307.07403", "2312.04018"} <= set(ids(with_replacements))

    replacements_only_own = fetch.merge(feeds, include_cross_lists=False, include_replacements=True)
    assert "2307.07403" in ids(replacements_only_own)  # replace
    assert "2312.04018" not in ids(replacements_only_own)  # replace-cross


def test_one_empty_feed_does_not_hide_the_others():
    feeds = [fetch.parse_feed(feed_bytes("empty.xml")), fetch.parse_feed(feed_bytes("astro-ph.IM.xml"))]
    merged = fetch.merge(feeds, include_cross_lists=True, include_replacements=False)
    assert merged.date == date(2024, 4, 9)


def test_fetch_announcement_reads_each_category():
    seen = []

    def fake_fetch(category):
        seen.append(category)
        return feed_bytes(f"{category}.xml")

    result = fetch.fetch_announcement(["astro-ph.CO", "astro-ph.IM"], fetch=fake_fetch)
    assert seen == ["astro-ph.CO", "astro-ph.IM"]
    assert len(result.papers) == 6


def fake_responses(monkeypatch, *responses):
    """Make http_get return each (status, body, error) in turn; returns the list of URLs requested."""
    urls, queue = [], list(responses)
    monkeypatch.setattr(fetch, "http_get", lambda url: urls.append(url) or queue.pop(0))
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    return urls


def test_bad_category_reports_arxivs_explanation(monkeypatch):
    fake_responses(monkeypatch, (400, feed_bytes("bad-category.xml"), ""))
    with pytest.raises(fetch.FetchError, match="Valid subject classes for the archive 'astro-ph'"):
        fetch.fetch_feed("astro-ph.XX")


def test_blocked_network_explains_the_cloud_allowlist(monkeypatch):
    fake_responses(monkeypatch, (0, b"", "curl: (56) CONNECT tunnel failed, response 403"))
    with pytest.raises(fetch.FetchError, match="add rss.arxiv.org to Allowed domains"):
        fetch.fetch_feed("astro-ph.CO")


def test_transient_errors_are_retried(monkeypatch):
    urls = fake_responses(monkeypatch, (0, b"", "connection reset"), (406, b"", ""), (200, b"<rss/>", ""))
    assert fetch.fetch_feed("astro-ph.CO") == b"<rss/>"
    assert urls == ["https://rss.arxiv.org/rss/astro-ph.CO"] * 3


def test_gives_up_after_retries(monkeypatch):
    fake_responses(monkeypatch, *[(503, b"", "")] * 3)
    with pytest.raises(fetch.FetchError, match="could not fetch .* HTTP 503"):
        fetch.fetch_feed("astro-ph.CO")


def test_http_get_prefers_curl(monkeypatch):
    calls = []

    def run(args, capture_output):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=b"<rss>\n</rss>\n200", stderr=b"")

    monkeypatch.setattr(fetch.shutil, "which", lambda name: "/usr/bin/curl")
    monkeypatch.setattr(fetch.subprocess, "run", run)
    assert fetch.http_get("https://rss.arxiv.org/rss/astro-ph.CO") == (200, b"<rss>\n</rss>", "")
    assert calls[0][0] == "curl" and fetch.USER_AGENT in calls[0]


def test_http_get_reports_curl_failures(monkeypatch):
    def run(args, capture_output):
        return subprocess.CompletedProcess(args, 56, stdout=b"\n000", stderr=b"curl: (56) CONNECT tunnel failed, response 403")

    monkeypatch.setattr(fetch.shutil, "which", lambda name: "/usr/bin/curl")
    monkeypatch.setattr(fetch.subprocess, "run", run)
    assert fetch.http_get("https://rss.arxiv.org/rss/x") == (0, b"", "curl: (56) CONNECT tunnel failed, response 403")


def test_http_get_falls_back_to_urllib(monkeypatch):
    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        assert request.get_header("User-agent") == fetch.USER_AGENT
        return Response(b"<rss/>")

    monkeypatch.setattr(fetch.shutil, "which", lambda name: None)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    assert fetch.http_get("https://rss.arxiv.org/rss/astro-ph.CO") == (200, b"<rss/>", "")

    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(b"why"))

    monkeypatch.setattr(fetch.urllib.request, "urlopen", refuse)
    assert fetch.http_get("https://rss.arxiv.org/rss/x")[:2] == (400, b"why")
