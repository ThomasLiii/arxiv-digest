# arxiv-digest

A daily arXiv digest built by a Claude Code scheduled task (routine) on the user's Claude plan. The task follows `ROUTINE.md`:

1. `python -m arxiv_digest prepare` fetches the latest announcement from arXiv's RSS feeds and writes batches plus `.digest/INSTRUCTIONS.md`.
2. Claude ranks every paper against `interests.md` and writes `.digest/scores-NN.json`.
3. `python -m arxiv_digest finish` validates the scores and writes `digests/<announcement date>.md`, which is pushed straight to main.

The design is routine-only by choice: no Anthropic API key, no API calls, no GitHub Actions digest workflow. Don't add an API-based path.

The code is in `arxiv_digest/`:

- `fetch.py`: RSS fetch, parse, and merge across categories.
- `triage.py`: ranking rules, how papers are shown to Claude, score validation.
- `routine.py`: the `.digest/` work directory (`prepare`/`collect`).
- `render.py`: the Markdown digest, plus the short summary a run ends with.
- `cli.py`: the `prepare` and `finish` subcommands.

## Working here

- Test with `pip install -e ".[dev]" && pytest`. Tests use the saved feeds in `tests/fixtures/` and stay offline.
- Runtime code is stdlib-only (Python 3.11+), so the cloud task runs `python -m arxiv_digest` with nothing installed. Keep it that way.
- Digests go directly to main by design; don't switch to PRs.
- When adding a setting, update `config.KEYS`, `digest.toml`, and the settings table in `README.md`.
- If you're asked to build today's digest in this repo, follow `ROUTINE.md`.
- New users set up their copy with the `/setup-digest` skill (`.claude/skills/setup-digest/SKILL.md`). Keep its steps in sync with the README's setup sections.
