"""Fetch recent arXiv submissions in specified categories.

Usage: python fetch_arxiv.py > today.json
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

CATEGORIES = ["astro-ph.CO", "astro-ph.IM", "astro-ph.GA", "cs.LG"]
LOOKBACK_HOURS = 36  # generous window to catch the last cycle
MAX_RESULTS = 200

NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

def fetch_category(cat: str):
    q = urlencode({
        "search_query": f"cat:{cat}",
        "start": 0,
        "max_results": MAX_RESULTS,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"https://export.arxiv.org/api/query?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 arxiv-digest"})
    delay = 5
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return ET.fromstring(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 5:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            raise

def parse_entry(e):
    get = lambda tag, ns="atom": (e.find(f"{ns}:{tag}", NS).text or "").strip()
    primary = e.find("arxiv:primary_category", NS).attrib["term"]
    cats = [c.attrib["term"] for c in e.findall("atom:category", NS)]
    authors = [a.find("atom:name", NS).text for a in e.findall("atom:author", NS)]
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

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    seen, papers = set(), []
    for i, cat in enumerate(CATEGORIES):
        if i > 0:
            time.sleep(3)
        root = fetch_category(cat)
        for entry in root.findall("atom:entry", NS):
            paper = parse_entry(entry)
            pub = datetime.fromisoformat(paper["published"].replace("Z", "+00:00"))
            if pub < cutoff or paper["id"] in seen:
                continue
            seen.add(paper["id"])
            papers.append(paper)
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(),
               "count": len(papers), "papers": papers},
              sys.stdout, indent=2)

if __name__ == "__main__":
    main()
