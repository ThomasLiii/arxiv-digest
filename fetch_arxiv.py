"""Fetch recent arXiv submissions in specified categories.

Usage: python fetch_arxiv.py > today.json
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
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
    # Use curl: arxiv's Fastly frontend returns 406 for HTTP/1.1 clients via
    # this environment's proxy, but works over HTTP/2 which curl negotiates.
    delay = 30
    for attempt in range(5):
        proc = subprocess.run(
            ["curl", "-sS", "-A", "arxiv-digest/1.0",
             "-w", "\n---HTTP-STATUS:%{http_code}---\n", url],
            capture_output=True, text=True, timeout=180,
        )
        body = proc.stdout
        marker = "\n---HTTP-STATUS:"
        idx = body.rfind(marker)
        status = 0
        if idx >= 0:
            try:
                status = int(body[idx + len(marker):].split("-", 1)[0])
            except ValueError:
                pass
            body = body[:idx]
        if proc.returncode != 0 or status >= 400:
            if status in (406, 429, 503) or proc.returncode != 0:
                if attempt < 4:
                    print(f"[{cat}] curl rc={proc.returncode} status={status}, retrying in {delay}s", file=sys.stderr)
                    time.sleep(delay)
                    delay = min(delay * 2, 240)
                    continue
            raise RuntimeError(f"curl failed rc={proc.returncode} status={status} stderr={proc.stderr[:400]}")
        return ET.fromstring(body)

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
            time.sleep(3)  # arxiv API asks for >=3s between requests
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
