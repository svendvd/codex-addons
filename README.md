# Codex Addons – Productivity Toolkit for the Codex CLI

`codex-addons` packages battle-tested utilities for developers who live inside the Codex CLI. The star of the toolkit is an interactive session explorer that helps you jump back into previous conversations in seconds.

## Why This Project Exists

- **Faster context switching:** Resume Codex CLI sessions from any repository without manually scraping JSON logs or remember your prompt (by using "codex resume")
- **Worktree aware:** Filter sessions by Git branch so multi-worktree setups stay tidy.

## Feature Highlights

| Feature | Description |
| --- | --- |
| Interactive picker | Arrow keys or `j`/`k` navigation with instant `codex resume <id>` execution. |
| Plain-text output | Use `--plain` in scripts, shell prompts, or TUIs. |
| Git branch filter | `--git` shows only sessions recorded on the current branch/repo, perfect for worktrees. |
| Safety switches | `--no-resume` prints the command instead of running it. |
| Lightweight install | Pure Python, no dependencies beyond the standard library. |

## Installation

Install directly from GitHub tags:

```bash
pip install --upgrade git+https://github.com/svendvd/codex-addons.git@v0.2.0
```

The install step registers a global CLI entry point called `codex-sessions`.

## Usage

```bash
codex-sessions                   # interactive picker
codex-sessions --plain --limit 5 # machine-friendly output
codex-sessions --git             # only show sessions for the current Git branch
codex-sessions --no-resume       # print, don’t execute, the resume command
```

Behind the scenes the CLI scans `~/.codex/sessions`, hoists the first meaningful user prompt, and formats results as `timestamp | session-id | cwd [branch] | prompt snippet`.

## Updating

1. Check the [releases](https://github.com/svendvd/codex-addons/tags) page for the latest tag.
2. Install it with `pip install --upgrade git+https://github.com/svendvd/codex-addons.git@vX.Y.Z`.
3. Your existing `codex-sessions` command picks up the new version automatically.

## Development Setup

```bash
pip install -e .
python3 -m codex_addons.list_sessions --help
```

Run the interactive picker locally with `python3 list_codex_sessions.py` or hit the package entry point as shown above.

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
