# Daily digest: steps for the Claude Code scheduled task

A scheduled task follows these steps each weekday to build the digest. (To set one up, see the README.) Run every command from the repository root. No installation is needed.

1. Run `python -m arxiv_digest prepare`.
   - If the output starts with "Nothing to do", stop. Don't commit anything. There is no announcement today, or today's digest already exists.
   - If it fails, stop and report the error. Don't commit anything.
2. Read `.digest/INSTRUCTIONS.md` and do exactly what it says. It holds the researcher's interests, the ranking rules, and where to write a scores file for each batch of papers. Read every paper in full, and rank them yourself. Don't write a script or use keyword matching to rank them.
3. Run `python -m arxiv_digest finish`.
   - If it lists papers without scores, add them to the scores files it names, then run it again.
4. Commit only the digest file that `finish` printed after "Digest:", using the commit message it printed, and push to the default branch:

   ```bash
   git add digests/<date>.md
   git commit -m "<commit message from finish>"
   git push origin HEAD:main
   ```

   If the repository's default branch isn't `main`, use its name instead. If the push is rejected because the branch has moved, run `git pull --rebase origin main` and push again. Don't push to a `claude/` branch, and don't open a pull request.
5. End by pasting the summary that `finish` printed: the high- and medium-priority papers.
