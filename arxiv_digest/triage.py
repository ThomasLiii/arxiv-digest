"""The ranking rules Claude follows, how papers are shown to it, and how its scores are checked."""
from __future__ import annotations

from dataclasses import dataclass

from .fetch import Paper

PRIORITIES = ("high", "medium", "low", "skip")
MAX_AUTHORS = 20  # collaboration papers can list hundreds

GUIDELINES = """\
You triage the day's new arXiv papers for a researcher, so they only spend time on what matters to them.

Their research interests:

<interests>
{interests}
</interests>

Give every paper one priority:
- "high": squarely on one of their high-priority interests; they would not want to miss it.
- "medium": clearly relevant to their work, or a partial but meaningful match to a high-priority interest.
- "low": tangential; worth a glance for context.
- "skip": not relevant, or in an area they asked to skip.

If the interests aren't grouped by priority, judge how central each paper is to them. Judge what a paper actually \
does, not keyword overlap. On a typical day most papers are "skip", and "high" should stay rare.

Also give each paper a "score" from 0 to 10 for ordering within its priority (10 = most relevant), and a "reason": \
for high, medium and low papers, one sentence under 25 words telling the researcher which of their interests it \
connects to and what is new. Use an empty string for skipped papers."""


@dataclass
class Score:
    priority: str
    score: int
    reason: str


def guidelines(interests: str) -> str:
    return GUIDELINES.replace("{interests}", interests.strip())


def format_papers(papers: list[Paper]) -> str:
    blocks = []
    for p in papers:
        authors = ", ".join(p.authors[:MAX_AUTHORS])
        if len(p.authors) > MAX_AUTHORS:
            authors += f", and {len(p.authors) - MAX_AUTHORS} others"
        blocks.append(
            f'<paper id="{p.id}">\n<title>{p.title}</title>\n<authors>{authors}</authors>\n'
            f"<categories>{', '.join(p.categories)}</categories>\n<abstract>{p.abstract}</abstract>\n</paper>"
        )
    return f"Triage these {len(papers)} papers.\n\n" + "\n\n".join(blocks)


def parse_scores(entries: object, ids: set[str]) -> dict[str, Score]:
    """Keep well-formed entries for known papers; anything else counts as unscored."""
    scores = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("id") not in ids or entry.get("priority") not in PRIORITIES:
            continue
        score = entry.get("score")
        scores[entry["id"]] = Score(
            priority=entry["priority"],
            score=max(0, min(10, score)) if isinstance(score, int) else 0,
            reason=str(entry.get("reason") or "").strip(),
        )
    return scores
