---
name: setup-digest
description: Set up this arXiv digest for a new user. Drafts their research interests, chooses arXiv categories, pushes their copy, and creates the Claude Code scheduled task that builds a digest every weekday.
disable-model-invocation: true
argument-hint: "[optional: arXiv links to papers you wrote or love]"
---

# Set up the arXiv digest

You're helping someone turn their copy of this repository into their own daily arXiv digest. When you're done:

- Their interests and categories are on `main`.
- A Claude Code scheduled task builds a digest every weekday by following `ROUTINE.md`.

Many users are researchers rather than software engineers. Explain each step in plain language, and ask before anything that changes their GitHub repository or Claude account.

## 1. Check that this is their own copy

Run `git remote get-url origin`. If it points at `ThomasLiii/arxiv-digest`, they're in the template itself, not their own copy, so stop and explain how to make one. Either:

- Click **Use this template → Create a new repository** on https://github.com/ThomasLiii/arxiv-digest, then clone the new repository.
- Or run `gh repo create my-arxiv-digest --template ThomasLiii/arxiv-digest --private --clone`.

Then they open Claude Code in the new folder and run `/setup-digest` again.

Also check that `python3 --version` is 3.11 or newer. The scheduled task's cloud machine has a suitable Python already. Locally it's only needed for the category check in step 3.

## 2. Draft their interests

Ask what they work on and what they want to keep up with.

If they gave arXiv links ($ARGUMENTS), or can share a few, read those papers to ground the draft. For example: `curl -s "https://export.arxiv.org/api/query?id_list=2404.04321,2404.04491"`.

Then rewrite `interests.md`:

- Keep its HTML comment at the top.
- Replace everything below it with their interests, grouped under `## High priority`, `## Medium priority`, `## Low priority / context` and `## Skip`.
- Be specific: methods, surveys, missions, object classes. "Strong-lens finding with CNNs in Euclid imaging" ranks papers far better than "lensing".
- Add conditions where they help, such as "(only if applied to imaging)".
- Use the Skip section for nearby topics they don't want to see.

Show them the draft and revise it until they're happy.

## 3. Choose categories

Propose the arXiv categories that cover their interests; the full list is at https://arxiv.org/category_taxonomy. Large categories like `cs.LG` and `cs.CV` add 100–250 papers a day and use more of their Claude plan, so suggest them only when the interests need them.

Once they agree, set `categories` in `digest.toml`. Leave the other settings alone unless they ask.

Check the category names with `python3 -m arxiv_digest prepare`. A typo produces an error that lists the valid codes. On a weekday this also writes a `.digest/` folder; delete it afterwards with `rm -rf .digest`.

## 4. Clear the template's history

Their copy came with the template author's past digests in `digests/`. Ask before deleting them, then run `git rm -q digests/*.md`.

## 5. Commit and push

Stage `interests.md` and `digest.toml` (the `git rm` in step 4 already staged the deleted digests) and commit with the message "Set up my arXiv digest". Then push to their default branch, usually with `git push origin HEAD:main`.

## 6. Create the scheduled task

Use these values:

- **Name:** arXiv digest
- **Prompt:** `Build today's arXiv digest by following ROUTINE.md in this repository. Commit the digest and push it directly to main. Don't push to a claude/ branch or open a pull request.`
- **Repository:** their copy, as `owner/name` from the origin URL.
- **Schedule:** cron `30 6 * * 1-5`, which is 06:30 UTC Monday to Friday, after arXiv's evening announcements reach its feeds.
- **Connectors:** none.

If this session has the `schedule` skill (`/schedule`), use it to create the task with those values. Otherwise, walk them through section 3 of `README.md` at https://claude.ai/code/routines.

## 7. Allow arXiv in the task's network settings

The default cloud environment blocks arxiv.org, so nothing works until the user changes this setting. It can only be done on the web. Walk them through it:

1. Open https://claude.ai/code/routines, click the task, open the menu next to its name, and choose **Edit**.
2. Go to **Advanced settings → General → Cloud environment** and click the environment's name.
3. Hover over the environment and click the settings icon.
4. Set **Network access** to **Custom** and enter `rss.arxiv.org` under **Allowed domains**.
5. Check **Also include default list of common package managers**, then click **Save changes**.

## 8. Test it

On a weekday, they can click **Run now** on the task's page and open the run from **History** to watch it. A finished run leaves `digests/<date>.md` on `main`. On weekends the run reports "Nothing to do", and the first digest arrives the next weekday morning.

Finish with a short summary of what's set up and anything they still need to do, such as step 7.
