"""Fetch the latest arXiv announcement from the per-category RSS feeds.

arXiv announces new papers Sunday-Thursday at 20:00 US Eastern. Each feed at
rss.arxiv.org holds exactly the most recent announcement for its category, and
is empty on days without one (weekends, holidays).
"""
from __future__ import annotations

import shutil
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Callable

FEED_URL = "https://rss.arxiv.org/rss/{category}"
USER_AGENT = "arxiv-digest/1.0 (+https://github.com/ThomasLiii/arxiv-digest)"
NS = {"arxiv": "http://arxiv.org/schemas/atom", "dc": "http://purl.org/dc/elements/1.1/"}
# When a paper shows up in several feeds, keep the most relevant listing, in this order.
ANNOUNCE_TYPES = ("new", "cross", "replace", "replace-cross")


class FetchError(Exception):
    pass


@dataclass
class Paper:
    id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    announce_type: str

    @property
    def primary_category(self) -> str:
        return self.categories[0] if self.categories else ""

    @property
    def url(self) -> str:
        return f"https://arxiv.org/abs/{self.id}"

    @property
    def pdf_url(self) -> str:
        return f"https://arxiv.org/pdf/{self.id}"


@dataclass
class Announcement:
    date: date | None  # None when there was no announcement
    papers: list[Paper]


def fetch_feed(category: str, retries: int = 3) -> bytes:
    url = FEED_URL.format(category=category)
    for attempt in range(retries):
        status, body, error = http_get(url)
        if status == 200:
            return body
        if status == 400:  # arXiv explains bad category names in the feed body
            raise FetchError(f"{category}: {_feed_error(body) or f'HTTP 400 from {url}'}")
        if status == 403 or "403" in error:  # the cloud environment's proxy refuses unlisted hosts
            raise FetchError(
                f"could not fetch {url} ({error or 'HTTP 403'}). In a Claude Code cloud environment, set "
                "Network access to Custom and add rss.arxiv.org to Allowed domains (see the README)."
            )
        if attempt < retries - 1:
            time.sleep(10 * 3**attempt)
    raise FetchError(f"could not fetch {url}: {error or f'HTTP {status}'}")


def http_get(url: str) -> tuple[int, bytes, str]:
    """GET a URL, returning (status, body, error message); status is 0 if no response arrived.

    Uses curl when it's installed: through the Claude Code cloud proxy, arXiv's CDN rejects
    HTTP/1.1 clients like urllib with 406, but accepts curl's HTTP/2.
    """
    if shutil.which("curl"):
        done = subprocess.run(
            ["curl", "-sS", "--max-time", "60", "-A", USER_AGENT, "-w", "\n%{http_code}", url], capture_output=True
        )
        body, _, code = done.stdout.rpartition(b"\n")
        status = int(code) if code.strip().isdigit() else 0
        return status, body, done.stderr.decode(errors="replace").strip()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, e.read(), str(e)
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, b"", str(e)


def parse_feed(xml: bytes) -> Announcement:
    try:
        channel = ET.fromstring(xml).find("channel")
    except ET.ParseError as e:
        raise FetchError(f"arXiv returned a malformed feed: {e}") from e
    if channel is None:
        raise FetchError("arXiv returned something that is not an RSS feed")
    pub_date = channel.findtext("pubDate")
    papers = [_parse_item(item) for item in channel.findall("item")]
    return Announcement(parsedate_to_datetime(pub_date).date() if pub_date else None, papers)


def merge(feeds: list[Announcement], *, include_cross_lists: bool, include_replacements: bool) -> Announcement:
    allowed = {"new"}
    if include_cross_lists:
        allowed.add("cross")
    if include_replacements:
        allowed.add("replace")
        if include_cross_lists:
            allowed.add("replace-cross")

    best: dict[str, Paper] = {}
    for feed in feeds:
        for paper in feed.papers:
            if paper.id not in best or _rank(paper) < _rank(best[paper.id]):
                best[paper.id] = paper
    dates = [feed.date for feed in feeds if feed.papers and feed.date]
    return Announcement(max(dates, default=None), [p for p in best.values() if p.announce_type in allowed])


def fetch_announcement(
    categories: list[str],
    *,
    include_cross_lists: bool = True,
    include_replacements: bool = False,
    fetch: Callable[[str], bytes] | None = None,
) -> Announcement:
    fetch = fetch or fetch_feed
    feeds = [parse_feed(fetch(category)) for category in categories]
    return merge(feeds, include_cross_lists=include_cross_lists, include_replacements=include_replacements)


def _parse_item(item: ET.Element) -> Paper:
    description = item.findtext("description", "")
    _, found, abstract = description.partition("Abstract:")
    creators = item.findtext("dc:creator", "", NS)
    return Paper(
        id=item.findtext("link", "").strip().split("/abs/", 1)[-1],
        title=" ".join(item.findtext("title", "").split()),
        abstract=" ".join((abstract if found else description).split()),
        authors=[name.strip() for name in creators.split(",") if name.strip()],
        categories=[c.text.strip() for c in item.findall("category") if c.text],
        announce_type=item.findtext("arxiv:announce_type", "new", NS).strip(),
    )


def _rank(paper: Paper) -> int:
    t = paper.announce_type
    return ANNOUNCE_TYPES.index(t) if t in ANNOUNCE_TYPES else len(ANNOUNCE_TYPES)


def _feed_error(body: bytes) -> str:
    try:
        return (ET.fromstring(body).findtext("channel/description") or "").strip()
    except ET.ParseError:
        return ""
