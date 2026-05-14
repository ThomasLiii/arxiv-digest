"""Fetch recent arXiv submissions in specified categories.

Usage: python fetch_arxiv.py > today.json
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

CATEGORIES = ["astro-ph.CO", "astro-ph.IM", "astro-ph.GA", "cs.LG"]
LOOKBACK_HOURS = 36
MAX_RESULTS = 200
UA = "Mozilla/5.0 arxiv-digest"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
RSS_NS = {"dc": "http://purl.org/dc/elements/1.1/", "arxiv": "http://arxiv.org/schemas/atom"}


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 5
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 5:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            raise


def fetch_atom_category(cat: str):
    q = urlencode({
        "search_query": f"cat:{cat}",
        "start": 0,
        "max_results": MAX_RESULTS,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    return ET.fromstring(_http_get(f"https://export.arxiv.org/api/query?{q}"))


def parse_atom_entry(e):
    get = lambda tag, ns="atom": (e.find(f"{ns}:{tag}", ATOM_NS).text or "").strip()
    primary = e.find("arxiv:primary_category", ATOM_NS).attrib["term"]
    cats = [c.attrib["term"] for c in e.findall("atom:category", ATOM_NS)]
    authors = [a.find("atom:name", ATOM_NS).text for a in e.findall("atom:author", ATOM_NS)]
    arxiv_id = get("id").rsplit("/", 1)[-1]
    return {
        "id": arxiv_id,
        "title": " ".join(get("title").split()),
        "abstract": " ".join(get("summary").split()),
        "authors": authors,
        "primary_category": primary,
        "categories": cats,
        "published": get("published"),
        "updated": get("updated"),
        "url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def fetch_rss_category(cat: str):
    return ET.fromstring(_http_get(f"https://rss.arxiv.org/rss/{cat}"))


def parse_rss_item(item, primary_default):
    link = (item.findtext("link") or "").strip()
    arxiv_id = link.rsplit("/", 1)[-1].split("v")[0] if link else ""
    title = " ".join((item.findtext("title") or "").split())
    desc = item.findtext("description") or ""
    desc = re.sub(r"^arXiv:\S+\s*Announce Type:\s*\S+\s*", "", desc).strip()
    if desc.lower().startswith("abstract:"):
        desc = desc[len("abstract:"):].strip()
    abstract = " ".join(desc.split())
    cats = [c.text for c in item.findall("category") if c.text]
    primary = cats[0] if cats else primary_default
    creator = item.findtext("dc:creator", default="", namespaces=RSS_NS)
    authors = [a.strip() for a in re.split(r",\s*", creator) if a.strip()]
    pub = item.findtext("pubDate") or ""
    try:
        pub_dt = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z").astimezone(timezone.utc).isoformat()
    except ValueError:
        pub_dt = pub
    return {
        "id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "primary_category": primary,
        "categories": cats,
        "published": pub_dt,
        "updated": pub_dt,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def fetch_via_atom():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    seen, papers = set(), []
    for i, cat in enumerate(CATEGORIES):
        if i > 0:
            time.sleep(3)
        root = fetch_atom_category(cat)
        for entry in root.findall("atom:entry", ATOM_NS):
            paper = parse_atom_entry(entry)
            pub = datetime.fromisoformat(paper["published"].replace("Z", "+00:00"))
            if pub < cutoff or paper["id"] in seen:
                continue
            seen.add(paper["id"])
            papers.append(paper)
    return papers


def fetch_via_rss():
    seen, papers = set(), []
    for i, cat in enumerate(CATEGORIES):
        if i > 0:
            time.sleep(3)
        root = fetch_rss_category(cat)
        for item in root.findall(".//item"):
            announce = item.findtext("{http://arxiv.org/schemas/atom}announce_type", default="")
            if announce and announce != "new":
                continue
            paper = parse_rss_item(item, primary_default=cat)
            if not paper["id"] or paper["id"] in seen:
                continue
            seen.add(paper["id"])
            papers.append(paper)
    return papers


def main():
    try:
        papers = fetch_via_atom()
    except urllib.error.HTTPError:
        papers = fetch_via_rss()
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(),
               "count": len(papers), "papers": papers},
              sys.stdout, indent=2)


if __name__ == "__main__":
    main()
