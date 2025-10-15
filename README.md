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

Use `--plain` to print the list without launching the interactive selector, or `--no-resume` to skip running the resume command automatically.

### Creating a shell alias

Add the following line to your shell configuration (e.g. `~/.zshrc`):
```bash
alias codex-sessions='python3 ~/codex-addons/list_codex_sessions.py'
```
Reload your shell (`source ~/.zshrc`) and invoke the tool anywhere with:
```bash
codex-sessions
```

Adjust the path in the alias if you moved the repository.
