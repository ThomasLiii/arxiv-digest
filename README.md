# arxiv-digest

Read only the arXiv papers that matter to you. Every weekday, a [Claude Code scheduled task](https://code.claude.com/docs/en/routines) takes the day's new papers in the categories you follow and ranks each one against a plain-English description of your research interests. It then commits a short Markdown digest to your repository:

- **High and medium priority:** title, authors, a one-line reason the paper matters *to you*, and the abstract one click away.
- **Low priority:** one line each.
- **Skipped:** a collapsed list, so you can check that nothing important slipped through.

It runs on your Claude plan (Pro, Max, Team or Enterprise). There's no API key and no extra bill.

## Quick setup (about 5 minutes)

1. **Make your own copy and open it in Claude Code:**

   ```bash
   gh repo create my-arxiv-digest --template ThomasLiii/arxiv-digest --private --clone
   cd my-arxiv-digest && claude
   ```

   Without the GitHub CLI, click **Use this template → Create a new repository** at the top of this page, then clone your new repository and open it in Claude Code.
2. **Run `/setup-digest`.** You can paste links to a few arXiv papers you've written or love, for example `/setup-digest https://arxiv.org/abs/2404.04321`. Claude will:
   - interview you and draft `interests.md`, then pick and check your categories;
   - clear out the template's old digests and push your copy;
   - create the scheduled task.
3. **Allow arXiv in the task's network settings.** This is the one step that has to be done on the web. `/setup-digest` walks you through it; the steps are the same as [step 3.4 below](#3-create-the-scheduled-task).

## Manual setup (about 10 minutes)

### 1. Make your own copy

At the top of this page, click **Use this template → Create a new repository**. The new repository can be public or private. Your copy comes with the template author's old digests, so delete them from `digests/`.

### 2. Describe your interests and categories

- **Interests:** edit [`interests.md`](interests.md). It's plain English: group topics under *High priority*, *Medium priority*, *Low priority* and *Skip*. See [Writing good interests](#writing-good-interests).
- **Categories:** edit `categories` in [`digest.toml`](digest.toml), for example `["astro-ph.CO", "astro-ph.GA"]`. All category codes are listed in the [arXiv category taxonomy](https://arxiv.org/category_taxonomy).

### 3. Create the scheduled task

1. Go to [claude.ai/code/routines](https://claude.ai/code/routines) and click **New task**. In some accounts the button reads **New routine**.
2. Name the task "arXiv digest" and paste this prompt:

   ```text
   Build today's arXiv digest by following ROUTINE.md in this repository. Commit the digest and push it directly to main. Don't push to a claude/ branch or open a pull request.
   ```

   Pick a model in the prompt box. Any current model works; Sonnet uses less of your plan than Opus.
3. Under **Advanced settings → General → Repository**, select your copy of this repository.
4. **Let the task reach arXiv.** The default cloud environment blocks arxiv.org.
   1. Under **Cloud environment**, click the environment's name (usually **Default**).
   2. Hover over it and click the settings icon.
   3. Set **Network access** to **Custom**, enter `rss.arxiv.org` under **Allowed domains**, and check **Also include default list of common package managers**.
   4. Click **Save changes**.
5. On the **Connectors** tab, remove every connector. The task doesn't need any.
6. Set **Trigger** to **Schedule** with any daily preset, then click **Create**.
7. **Set the schedule.** Open the task's menu, choose **Edit**, select **Custom**, enter `30 6 * * 1-5`, and save. That's 06:30 UTC, Monday through Friday: soon after arXiv's evening announcements reach its feeds. A weekday preset in your local time zone works too, if it falls between 06:00 and 20:00 UTC (in the Americas and Europe, any weekday morning).

You can also create the task by running `/schedule` in Claude Code, which walks you through the same steps. You still need to do step 4 (network access) on the web.

### 4. Test it

On a weekday, click **Run now** on the task's page, then open the run from **History** to watch it. When it finishes, `digests/<date>.md` is on `main` and the session ends with the day's top papers. On weekends arXiv doesn't announce, so the run just reports that there's nothing to do.

## Reading your digest

- **In the repository:** `digests/` has one file per announcement day, and GitHub renders the math in titles and abstracts.
- **In the run's session:** each run, which you can open on claude.ai or in the Claude app, ends with the day's high- and medium-priority papers.

## Customizing

### Writing good interests

Claude reads [`interests.md`](interests.md) word for word. HTML `<!-- comments -->` are removed first, so you can leave notes to yourself there. Some tips:

- **Be specific.** "Strong-lens finding with CNNs in Euclid imaging" ranks papers much better than "gravitational lensing".
- **Use *Skip*.** Name the nearby topics you never want to see, such as "exoplanets" or "pure-theory inflation models".
- **Add conditions.** For example: "General ML methods (only if directly applicable to imaging)".
- **Tune it.** After a few days, look at what landed in each section and adjust the wording. Changes take effect on the next run.

### Settings

All settings live in [`digest.toml`](digest.toml):

| Setting | Default | What it does |
|---|---|---|
| `categories` | (required) | arXiv listings to read, e.g. `["astro-ph.CO", "cs.CV"]`. |
| `include_cross_lists` | `true` | Also include papers from other fields that authors cross-listed into your categories. |
| `include_replacements` | `false` | Also include revised versions (v2, v3, …) of older papers. |
| `interests_file` | `"interests.md"` | Where your interests live. |
| `batch_size` | `40` | Papers per file that Claude reads and scores in one go. |
| `output.directory` | `"digests"` | Where digests are written. |
| `output.list_skipped` | `true` | Add the collapsed list of skipped papers. |

The model is whichever one you picked when you created the task. To change it or the schedule, edit the task at [claude.ai/code/routines](https://claude.ai/code/routines).

### Plan usage

Each run counts against your plan's usage like any other Claude Code session. Claude reads about 400 tokens per paper (title, authors and abstract), so the categories you pick matter most. For example, three astro-ph categories come to about 85 papers a day; adding `cs.LG` brings that to about 290. The task runs at night, so it rarely competes with your own work. Check your usage at [claude.ai/settings/usage](https://claude.ai/settings/usage).

## Running it by hand

Open Claude Code in your copy and ask it to "follow ROUTINE.md". It runs the same steps as the scheduled task, using your plan. You need Python 3.11 or newer, with nothing to install.

## How it works

[`ROUTINE.md`](ROUTINE.md) holds the steps the task follows:

1. **Fetch.** `python -m arxiv_digest prepare` reads `https://rss.arxiv.org/rss/<category>` for each category. Each feed holds exactly the most recent announcement: new papers, cross-lists and replacements. A paper listed in several of your categories is counted once. `prepare` writes the papers in batches to `.digest/`, along with `INSTRUCTIONS.md`, which holds your interests and the ranking rules.
2. **Rank.** Claude reads every batch and writes a scores file for each, giving every paper a priority, a 0–10 score and a one-line reason.
3. **Check and write.** `python -m arxiv_digest finish` checks that every paper has a valid score and names any that are missing so Claude can fill them in. It then writes `digests/<announcement date>.md`, and the task commits it to `main`.

Each announcement is processed only once: if today's digest already exists, the run does nothing. The scripts use only the Python standard library, so the task installs nothing.

arXiv announces new papers Sunday through Thursday at 20:00 US Eastern, and the feeds update a few hours later. Running at 06:30 UTC Monday through Friday picks up each announcement.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Nothing to do: no arXiv announcement" | Normal on weekends and arXiv holidays. |
| "this machine's network blocks rss.arxiv.org" or HTTP 403 | Allow `rss.arxiv.org` in the task's environment (step 3.4). |
| The digest landed on a `claude/` branch or in a pull request | The task's prompt must say to push directly to `main`, as in step 3.2. Also check that no branch protection rule on `main` blocks your own pushes. |
| No digest appeared | Open the run from the task's **History**. A run marked as succeeded can still have stopped early, and its transcript says why. |
| "Bad subject class …" | There's a typo in `categories`. The error lists the valid codes. |
| A weekday digest is missing | Click **Run now** *the same day*. The feeds only hold the latest announcement, so a missed day can't be fetched later. |
| The task stopped running | If your GitHub connection expires for more than 72 hours, the task turns off. Reconnect GitHub, then turn the task back on. |

## Development

```bash
pip install -e ".[dev]"
pytest
```

The tests use saved arXiv feeds, so they never touch the network. The code lives in `arxiv_digest/`:

| File | Role |
|---|---|
| `fetch.py` | Reads the arXiv RSS feeds. |
| `triage.py` | The ranking rules and score checks. |
| `routine.py` | The `.digest/` work directory behind `prepare` and `finish`. |
| `render.py` | Writes the Markdown digest. |
| `cli.py` | The `prepare` and `finish` commands. |
