"""Render a scored announcement as Markdown."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .fetch import Paper
from .triage import Score

SECTIONS = (("high", "High priority"), ("medium", "Medium priority"), ("low", "Low priority"))
SHOWN_AUTHORS = 4


@dataclass
class Digest:
    date: date
    papers: list[Paper]
    scores: dict[str, Score]
    categories: list[str]

    def ranked(self, priority: str) -> list[Paper]:
        group = [p for p in self.papers if p.id in self.scores and self.scores[p.id].priority == priority]
        return sorted(group, key=lambda p: -self.scores[p.id].score)

    def unscored(self) -> list[Paper]:
        return [p for p in self.papers if p.id not in self.scores]

    def counts(self) -> str:
        return " · ".join(f"{len(self.ranked(key))} {key}" for key, _ in SECTIONS)

    def title(self) -> str:
        return f"arXiv digest — {self.date:%A} {self.date.day} {self.date:%B %Y}"

    def commit_message(self) -> str:
        return f"digest: {self.date} ({self.counts()})"


def render(digest: Digest, *, list_skipped: bool = True) -> str:
    lines = [
        f"# {digest.title()}",
        "",
        f"**{digest.counts()}** of {len(digest.papers)} papers announced in {', '.join(digest.categories)}.",
    ]
    for key, heading in SECTIONS:
        papers = digest.ranked(key)
        lines += ["", f"## {heading}", ""]
        if not papers:
            lines.append("_Nothing today._")
        elif key == "low":
            lines += [f"- {_link(p)} — {digest.scores[p.id].reason} · {_category(p)}" for p in papers]
        else:
            for i, p in enumerate(papers):
                lines += ([""] if i else []) + _entry(p, digest.scores[p.id].reason)

    unscored = digest.unscored()
    if unscored:
        lines += [
            "",
            f"## Not scored ({len(unscored)})",
            "",
            "These papers were left without a score. They're listed so nothing is silently dropped.",
            "",
        ]
        lines += [f"- {_link(p)} · {_category(p)}" for p in unscored]

    skipped = digest.ranked("skip")
    if list_skipped and skipped:
        lines += ["", f"<details><summary>Skipped ({len(skipped)})</summary>", ""]
        lines += [f"- {_link(p)} · {_category(p)}" for p in skipped]
        lines += ["", "</details>"]

    lines += ["", "---", "", "<sub>Ranked by Claude Code.</sub>", ""]
    return "\n".join(lines)


def render_brief(digest: Digest) -> str:
    """High and medium papers only: the summary a run ends with."""
    lines = [f"**{digest.counts()}** of {len(digest.papers)} papers."]
    for key, heading in SECTIONS[:2]:
        papers = digest.ranked(key)
        if papers:
            lines += ["", f"### {heading}", ""]
            lines += [f"- **{_link(p)}** — {digest.scores[p.id].reason}" for p in papers]
    return "\n".join(lines) + "\n"


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _entry(paper: Paper, reason: str) -> list[str]:
    authors = ", ".join(paper.authors[:SHOWN_AUTHORS])
    if len(paper.authors) > SHOWN_AUTHORS:
        authors += " et al."
    return [
        f"### {_link(paper)}",
        "",
        f"{authors} · {_category(paper)} · [PDF]({paper.pdf_url})",
        "",
        f"**Why:** {reason}",
        "",
        "<details><summary>Abstract</summary>",
        "",
        paper.abstract,
        "",
        "</details>",
    ]


def _link(paper: Paper) -> str:
    title = paper.title.replace("[", r"\[").replace("]", r"\]")
    return f"[{title}]({paper.url})"


def _category(paper: Paper) -> str:
    label = f"`{paper.primary_category}`"
    if paper.announce_type.startswith("replace"):
        label += " (revised)"
    return label
