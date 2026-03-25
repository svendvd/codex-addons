"""Launch the packaged Node-based codex usage status helper."""
from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.resources import as_file, files


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    node = shutil.which("node")
    if node is None:
        print(
            "node is required for `codex-usage-status` but was not found on PATH.",
            file=sys.stderr,
        )
        return 1

    script = files("codex_addons").joinpath("codex-usage-status.mjs")
    with as_file(script) as script_path:
        completed = subprocess.run([node, str(script_path), *args], check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
