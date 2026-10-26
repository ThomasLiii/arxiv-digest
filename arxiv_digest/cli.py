"""Command-line entry point, run by a Claude Code session following ROUTINE.md.

`prepare` fetches the latest announcement and writes ranking instructions; the session ranks the
papers; `finish` checks the scores and writes the digest.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__, config, fetch, render, routine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arxiv-digest",
        description="Rank today's arXiv announcement against your research interests and write a Markdown digest.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="digest.toml", help="settings file (default: %(default)s)")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    prepare = commands.add_parser(
        "prepare", parents=[common], help="fetch today's papers and write ranking instructions to .digest/"
    )
    prepare.add_argument("--force", action="store_true", help="prepare even if today's digest already exists")

    finish = commands.add_parser("finish", parents=[common], help="check the scores and write the digest")
    finish.add_argument("--allow-missing", action="store_true", help="write the digest even if some papers lack scores")

    args = parser.parse_args(argv)
    try:
        return {"prepare": _prepare, "finish": _finish}[args.command](args)
    except (config.ConfigError, fetch.FetchError, routine.RoutineError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _prepare(args: argparse.Namespace) -> int:
    cfg = config.load(args.config)
    print(f"Fetching the latest arXiv announcement for {', '.join(cfg.categories)}...", file=sys.stderr)
    announcement = fetch.fetch_announcement(
        cfg.categories,
        include_cross_lists=cfg.include_cross_lists,
        include_replacements=cfg.include_replacements,
    )
    if announcement.date is None:
        print("Nothing to do: no arXiv announcement right now (arXiv doesn't announce on weekends or holidays).")
        return 0
    path = cfg.output_dir / f"{announcement.date.isoformat()}.md"
    if path.exists() and not args.force:
        print(f"Nothing to do: {path.as_posix()} already exists. Use --force to rebuild it.")
        return 0

    work = Path(args.config).parent / routine.WORK_DIR
    batches = routine.prepare(announcement, cfg.interests, cfg.batch_size, work)
    print(
        f"Ready: {len(announcement.papers)} papers from {announcement.date} in {render.plural(batches, 'batch file')}. "
        f"Next: read {(work / 'INSTRUCTIONS.md').as_posix()} and follow it."
    )
    return 0


def _finish(args: argparse.Namespace) -> int:
    cfg = config.load(args.config)
    work = Path(args.config).parent / routine.WORK_DIR
    announcement, scores, missing = routine.collect(work)
    if missing and not args.allow_missing:
        print("These papers have no score yet:")
        for name, ids in missing.items():
            print(f"  {name}: {', '.join(ids)}")
        print("Add them to those files and run finish again, or pass --allow-missing to list them as unscored.")
        return 2
    if announcement.papers and not scores:
        raise routine.RoutineError("no papers have scores yet; follow INSTRUCTIONS.md first")

    digest = render.Digest(announcement.date, announcement.papers, scores, cfg.categories)
    path = cfg.output_dir / f"{digest.date.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render.render(digest, list_skipped=cfg.list_skipped), encoding="utf-8")
    shutil.rmtree(work)
    print(f"Digest: {path.as_posix()}")
    print(f"Commit message: {digest.commit_message()}")
    print()
    print(render.render_brief(digest))
    return 0
