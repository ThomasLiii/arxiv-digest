"""The work directory a Claude Code session ranks papers in, between `prepare` and `finish`.

`prepare` writes the day's papers and ranking instructions to the work directory. The session reads them
and writes one scores file per batch. `finish` checks those files and renders the digest.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .fetch import Announcement, Paper
from .triage import Score, format_papers, guidelines, parse_scores

WORK_DIR = ".digest"


class RoutineError(Exception):
    pass


def prepare(announcement: Announcement, interests: str, batch_size: int, work: Path) -> int:
    """Write the work directory and return how many batch files it holds."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    papers = announcement.papers
    batches = [papers[i : i + batch_size] for i in range(0, len(papers), batch_size)]
    for n, batch in enumerate(batches, 1):
        (work / f"batch-{n:02}.md").write_text(format_papers(batch) + "\n", encoding="utf-8")
    state = {
        "date": announcement.date.isoformat(),
        "batches": [[p.id for p in batch] for batch in batches],
        "papers": [asdict(p) for p in papers],
    }
    (work / "announcement.json").write_text(json.dumps(state, indent=1), encoding="utf-8")
    (work / "INSTRUCTIONS.md").write_text(_instructions(announcement, interests, work, len(batches)), encoding="utf-8")
    return len(batches)


def collect(work: Path) -> tuple[Announcement, dict[str, Score], dict[str, list[str]]]:
    """Read the session's scores. Returns the announcement, the scores, and missing ids per scores file."""
    state_path = work / "announcement.json"
    if not state_path.is_file():
        raise RoutineError(f"{state_path} not found. Run `python -m arxiv_digest prepare` first.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    papers = [Paper(**p) for p in state["papers"]]
    ids = {p.id for p in papers}

    scores: dict[str, Score] = {}
    for path in sorted(work.glob("scores-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise RoutineError(f"{path} is not valid JSON ({e}). Fix it and run finish again.") from e
        scores.update(parse_scores(data.get("papers") if isinstance(data, dict) else data, ids))

    missing = {}
    for n, batch in enumerate(state["batches"], 1):
        absent = [i for i in batch if i not in scores]
        if absent:
            missing[f"scores-{n:02}.json"] = absent
    return Announcement(date.fromisoformat(state["date"]), papers), scores, missing


def _instructions(announcement: Announcement, interests: str, work: Path, batches: int) -> str:
    folder = work.as_posix()
    where = (
        f"in `{folder}/batch-01.md`"
        if batches == 1
        else f"in {batches} files, `{folder}/batch-01.md` to `{folder}/batch-{batches:02}.md`. Work through them in order"
    )
    example = (
        '{"papers": [{"id": "2404.04321", "priority": "medium", "score": 6, '
        '"reason": "One sentence: which of their interests it connects to and what is new."}]}'
    )
    return f"""# Rank the arXiv announcement of {announcement.date}

{guidelines(interests)}

## Where the papers are and what to write

There are {len(announcement.papers)} papers {where}. For each `batch-NN.md`, read the whole file, then write \
`{folder}/scores-NN.json` with one entry per paper in that batch, its id copied exactly, in this shape:

```json
{example}
```

- "priority" is one of "high", "medium", "low", "skip".
- "score" is an integer from 0 to 10.
- "reason" is an empty string for skipped papers.

When every batch has its scores file, run `python -m arxiv_digest finish`.
"""
