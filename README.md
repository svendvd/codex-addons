# codex-addons

Utilities that augment the Codex CLI workflow.

## Tools

- `list_codex_sessions.py` – Lists recent Codex CLI sessions scoped to the current project. Supports interactive selection (arrow keys / `j` `k`) and will run `codex resume <id>` for the chosen session.

## Installation

1. Ensure Python 3.10+ is available (`python3 --version`).
2. Clone the repository into a location on your machine:
   ```bash
   git clone git@github.com:svendvd/codex-addons.git
   cd codex-addons
   ```
3. (Optional) Install dependencies into a virtual environment; the script uses only the Python standard library.

### Running the tool

Run the script directly from the repository root:
```bash
python3 list_codex_sessions.py
```

Useful flags:
- `--plain` prints matches without launching the interactive selector.
- `--no-resume` skips executing `codex resume` and prints the command instead.
- `--git` limits the list to sessions that match your current Git branch (and repository when known), so alternate worktrees stay focused on the same branch history.

### Creating a shell alias

Add the following line to your shell configuration (e.g. `~/.zshrc`):
```bash
alias codex-sessions='python3 ~/codex_addon/list_codex_sessions.py'
```
Reload your shell (`source ~/.zshrc`) and invoke the tool anywhere with:
```bash
codex-sessions
```

Adjust the path in the alias if you moved the repository.
