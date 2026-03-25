# Codex Addons – Productivity Toolkit for the Codex CLI

`codex-addons` packages battle-tested utilities for developers who live inside the Codex CLI. It currently ships two focused helpers: an interactive session explorer and a rollout usage status inspector.

## Why This Project Exists

- **Faster context switching:** Resume Codex CLI sessions from any repository without manually scraping JSON logs or remember your prompt (by using "codex resume")
- **Worktree aware:** Filter sessions by Git branch so multi-worktree setups stay tidy.
- **Quota visibility:** Inspect the latest Codex rollout rate limits without digging through SQLite and JSONL files by hand.

## Feature Highlights

| Feature | Description |
| --- | --- |
| Interactive picker | Arrow keys or `j`/`k` navigation with instant `codex resume <id>` execution. |
| Plain-text output | Use `--plain` in scripts, shell prompts, or TUIs. |
| Git branch filter | `--git` shows only sessions recorded on the current branch/repo, perfect for worktrees. |
| Usage budget snapshot | `codex-usage-status` inspects the latest rollout rate limits and summarizes reset windows plus a daily remaining-budget formula. |
| Safety switches | `--no-resume` prints the command instead of running it. |
| Privacy-aware output | `codex-usage-status --json` omits absolute local paths by default and only shows `~`-redacted paths when explicitly requested. |

## Installation

Install directly from GitHub:

```bash
pip install --upgrade git+https://github.com/svendvd/codex-addons.git
```

The install step registers two global CLI entry points:

- `codex-sessions`
- `codex-usage-status`

`codex-usage-status` additionally requires `node` and the `sqlite3` CLI on your `PATH`.

## Usage

```bash
codex-sessions                   # interactive picker
codex-sessions --plain --limit 5 # machine-friendly output
codex-sessions --git             # only show sessions for the current Git branch
codex-sessions --no-resume       # print, don’t execute, the resume command

codex-usage-status               # human-readable rate-limit summary for source=exec
codex-usage-status --json        # machine-readable status payload
codex-usage-status --source=my-source # inspect a non-default rollout source
codex-usage-status --daily-budget-percent=10 --daily-cutoff-hour=20
codex-usage-status --show-paths --json
```

Behind the scenes the CLI scans `~/.codex/sessions`, hoists the first meaningful user prompt, and formats results as `timestamp | session-id | cwd [branch] | prompt snippet`.

`codex-usage-status` resolves the latest Codex state database inside `CODEX_HOME` (or `~/.codex`), follows the latest rollout for the selected source, and reads the newest `token_count` event with `rate_limits`.

The daily-left formula is configurable through `--daily-budget-percent` and `--daily-cutoff-hour`, so you can tune the subtraction logic without editing the script.

The JSON output deliberately excludes absolute filesystem paths. If you need troubleshooting details, add `--show-paths`; the command then emits `~`-redacted paths instead of raw home-directory locations.

## Updating

1. Check the [releases](https://github.com/svendvd/codex-addons/tags) page for the latest tag.
2. Install it with `pip install --upgrade git+https://github.com/svendvd/codex-addons.git@vX.Y.Z`.
3. Your existing `codex-sessions` and `codex-usage-status` commands pick up the new version automatically.

## Development Setup

```bash
pip install -e .
python3 -m codex_addons.list_sessions --help
python3 -m codex_addons.usage_status --help
```

Run the interactive picker locally with `python3 list_codex_sessions.py` or hit the package entry points as shown above.

## Release Workflow

1. Bump the version in `codex_addons/__init__.py` and `pyproject.toml`.
2. `git commit` the changes and tag them (`git tag v0.3.0`).
3. `git push origin main --tags` – GitHub Actions builds wheels via `.github/workflows/release.yml` and attaches them to the release so users can upgrade with a single pip command.

## Roadmap Ideas

- richer search (prompt text, directory focus, custom limits)
- additional Codex CLI helpers (command history, telemetry analyzers, auto switch to worktree/branch)
- optional SQLite cache for faster lookups on huge session directories

## License

MIT © Sven Nähler – Contributions welcome!
