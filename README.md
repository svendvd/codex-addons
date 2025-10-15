# codex-addons

Utilities that augment the Codex CLI workflow.

## Installation

Grab the latest tag from the repository and install it directly with `pip` (or `pipx`). Example for version `0.2.0`:

```bash
pip install --upgrade git+https://github.com/svendvd/codex-addons.git@v0.2.0
```

After installation a `codex-sessions` command is available automatically. You can still run the script directly:

```bash
python3 -m codex_addons.list_sessions
```

## Tools

- `list_sessions` – Lists recent Codex CLI sessions scoped to the current project. Supports interactive selection (arrow keys / `j` `k`) and will run `codex resume <id>` for the chosen session. Use `--plain` for non-interactive mode, `--no-resume` to skip executing the command, and `--git` to restrict results to sessions recorded on the current Git branch.

## Development

```bash
pip install -e .
python3 -m codex_addons.list_sessions --help
```

## Release workflow

1. Update `codex_addons/__init__.py` and `pyproject.toml` with the new version.
2. Commit the changes and tag them (e.g. `git tag v0.3.0`).
3. Push the tag (`git push origin --tags`). The GitHub release workflow builds the wheel and attaches it to the GitHub release so users can upgrade with `pip install --upgrade git+https://github.com/svendvd/codex-addons.git@v0.3.0`.
