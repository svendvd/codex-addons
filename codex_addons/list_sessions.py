#!/usr/bin/env python3
"""List Codex CLI sessions relevant to the current working directory."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

SESSIONS_ROOT = Path.home() / ".codex" / "sessions"
MAX_PROMPT_LENGTH = 160
TAG_PATTERN = re.compile(r"<[^>]+>")
NOISE_PREFIXES = (
    "<environment_context",
    "<user_instructions",
    "<system_instructions",
    "<codex_resume",
)


@dataclass
class SessionSummary:
    timestamp: datetime
    cwd: Path
    file_path: Path
    prompt: str
    session_id: str
    git_branch: Optional[str] = None
    git_repository: Optional[str] = None


@dataclass(frozen=True)
class GitContext:
    branch: Optional[str]
    repository: Optional[str]


def find_session_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return iter(())
    return (path for path in root.rglob("*.jsonl") if path.is_file())


def is_relevant_session(session_cwd: Path, current_dir: Path) -> bool:
    session_cwd = session_cwd.resolve()
    current_dir = current_dir.resolve()
    try:
        current_dir.relative_to(session_cwd)
        return True
    except ValueError:
        pass
    try:
        session_cwd.relative_to(current_dir)
        return True
    except ValueError:
        return False


def parse_timestamp(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def extract_prompt(content: Iterable[dict]) -> str:
    parts: List[str] = []
    for block in content:
        text = block.get("text")
        if text:
            parts.append(text.strip())
    return "\n".join(part for part in parts if part)


def is_noise_prompt(prompt: str) -> bool:
    stripped = prompt.lstrip()
    if not stripped:
        return True
    lower = stripped.lower()
    return any(lower.startswith(prefix) for prefix in NOISE_PREFIXES)


def summarize_prompt(prompt: str, max_length: int = MAX_PROMPT_LENGTH) -> str:
    cleaned = TAG_PATTERN.sub(" ", prompt)
    meaningful_line: Optional[str] = None
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        meaningful_line = line
        break
    if meaningful_line is None:
        meaningful_line = " ".join(cleaned.split())
    summary = " ".join(meaningful_line.split())
    if not summary:
        return ""
    if len(summary) > max_length:
        summary = summary[: max_length - 1].rstrip() + "…"
    return summary


def load_session(file_path: Path) -> Optional[SessionSummary]:
    session_meta = None
    first_user_prompt: Optional[str] = None

    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")

            if event_type == "session_meta":
                session_meta = event
            elif (
                event_type == "response_item"
                and event.get("payload", {}).get("type") == "message"
                and event["payload"].get("role") == "user"
            ):
                candidate_prompt = extract_prompt(event["payload"].get("content", []))
                if is_noise_prompt(candidate_prompt):
                    continue
                if summarize_prompt(candidate_prompt):
                    first_user_prompt = candidate_prompt
                    break

    if not session_meta or not first_user_prompt:
        return None

    payload = session_meta.get("payload", {})
    raw_cwd = payload.get("cwd")
    raw_timestamp = payload.get("timestamp") or session_meta.get("timestamp")
    session_id = payload.get("id") or session_meta.get("id", "")
    git_info = payload.get("git", {})

    if not raw_cwd or not raw_timestamp:
        return None

    try:
        timestamp = parse_timestamp(raw_timestamp)
    except ValueError:
        return None

    prompt = first_user_prompt.strip()
    if not prompt:
        return None

    return SessionSummary(
        timestamp=timestamp,
        cwd=Path(raw_cwd).expanduser().resolve(),
        file_path=file_path,
        prompt=prompt,
        session_id=str(session_id),
        git_branch=git_info.get("branch"),
        git_repository=git_info.get("repository_url"),
    )


def normalize_repo_identifier(identifier: Optional[str]) -> Optional[str]:
    if not identifier:
        return None
    value = identifier.strip()
    if not value:
        return None

    if value.startswith("git@"):
        value = value[4:]
        if ":" in value:
            user, rest = value.split(":", 1)
            value = f"{user}/{rest}"
    elif "://" in value:
        value = value.split("://", 1)[1]

    if value.startswith("~") or value.startswith("/"):
        value = str(Path(value).expanduser().resolve())
    else:
        value = value.strip("/")

    if value.endswith(".git"):
        value = value[:-4]

    return value.lower()


@lru_cache(maxsize=None)
def detect_git_metadata(path_str: str) -> GitContext:
    path = Path(path_str)
    if not path.exists():
        return GitContext(branch=None, repository=None)

    branch: Optional[str] = None
    repository: Optional[str] = None

    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        branch = None

    try:
        remote_result = subprocess.run(
            ["git", "-C", str(path), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        repository = remote_result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        repository = None

    if repository is None:
        try:
            top_result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repository = top_result.stdout.strip() or None
        except (subprocess.CalledProcessError, FileNotFoundError):
            repository = None

    return GitContext(branch=branch, repository=repository)


def repo_matches(session_repo: Optional[str], context_repo: Optional[str]) -> bool:
    if not context_repo:
        return True
    if not session_repo:
        return True
    return normalize_repo_identifier(session_repo) == normalize_repo_identifier(context_repo)


def format_summary_line(summary: SessionSummary) -> str:
    local_ts = summary.timestamp.astimezone()
    branch_segment = f" [{summary.git_branch}]" if summary.git_branch else ""
    prompt_line = summarize_prompt(summary.prompt)
    return (
        f"{local_ts:%Y-%m-%d %H:%M:%S %Z} | {summary.session_id} | "
        f"{summary.cwd}{branch_segment} | {prompt_line}"
    )


def gather_summaries(
    current_dir: Path,
    limit: Optional[int],
    git_context: Optional[GitContext],
    require_git_lookup: bool,
) -> List[SessionSummary]:
    summaries: List[SessionSummary] = []

    for file_path in find_session_files(SESSIONS_ROOT):
        summary = load_session(file_path)
        if not summary:
            continue

        if git_context and require_git_lookup and (
            summary.git_branch is None
            or (git_context.repository and summary.git_repository is None)
        ):
            metadata = detect_git_metadata(str(summary.cwd))
            if summary.git_branch is None:
                summary.git_branch = metadata.branch
            if summary.git_repository is None:
                summary.git_repository = metadata.repository

        path_match = is_relevant_session(summary.cwd, current_dir)

        include = path_match

        if git_context:
            if git_context.branch:
                branch_ok = summary.git_branch == git_context.branch
                repo_ok = repo_matches(summary.git_repository, git_context.repository)
                include = branch_ok and repo_ok
            elif git_context.repository:
                include = path_match or repo_matches(summary.git_repository, git_context.repository)

        if not include:
            continue

        summaries.append(summary)

    summaries.sort(key=lambda item: item.timestamp, reverse=True)

    if limit is not None:
        return summaries[:limit]
    return summaries


def interactive_select(
    summaries: List[SessionSummary],
    allow_delete: bool = False,
    delete_handler=None,
) -> Optional[SessionSummary]:
    import curses

    def _inner(stdscr):
        curses.curs_set(0)
        curses.use_default_colors()
        current = 0
        top = 0
        total = len(summaries)
        status_message: Optional[str] = None

        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            visible = max(1, height - 2)

            if current < top:
                top = current
            elif current >= top + visible:
                top = current - visible + 1

            for idx in range(visible):
                pos = top + idx
                if pos >= total:
                    break
                line = format_summary_line(summaries[pos])
                truncated = line[:width - 1]
                if pos == current:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(idx, 0, truncated)
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(idx, 0, truncated)

            status = "↑/↓ select • Enter confirm • q to quit"
            if allow_delete:
                status += " • d delete"
            stdscr.addstr(height - 1, 0, status[: width - 1])

            if status_message:
                stdscr.addstr(height - 2, 0, status_message[: width - 1])
                status_message = None
            stdscr.refresh()

            try:
                key = stdscr.getch()
            except KeyboardInterrupt:
                return None

            if key in (curses.KEY_UP, ord("k")):
                current = (current - 1) % total
            elif key in (curses.KEY_DOWN, ord("j")):
                current = (current + 1) % total
            elif key in (curses.KEY_PPAGE,):
                current = max(current - visible, 0)
            elif key in (curses.KEY_NPAGE,):
                current = min(current + visible, total - 1)
            elif key in (curses.KEY_ENTER, 10, 13):
                return summaries[current]
            elif allow_delete and key in (ord("d"), ord("D")) and delete_handler:
                target = summaries[current]
                prompt = f"Delete {target.session_id}? (y/n)"

                while True:
                    stdscr.addstr(height - 2, 0, " " * (width - 1))
                    stdscr.addstr(height - 2, 0, prompt[: width - 1])
                    stdscr.refresh()

                    try:
                        choice = stdscr.getch()
                    except KeyboardInterrupt:
                        status_message = "Deletion cancelled."
                        break

                    if choice in (ord("y"), ord("Y")):
                        deleted, notice = delete_handler(target)
                        status_message = notice
                        if deleted:
                            summaries.pop(current)
                            total -= 1
                            if total == 0:
                                return None
                            if current >= total:
                                current = total - 1
                        break

                    if choice in (ord("n"), ord("N"), 27):
                        status_message = "Deletion cancelled."
                        break

                continue
            elif key in (27, ord("q")):
                return None

    try:
        return curses.wrapper(_inner)
    except KeyboardInterrupt:
        return None


def run_codex_resume(session_id: str) -> int:
    try:
        result = subprocess.run(["codex", "resume", session_id])
    except FileNotFoundError:
        print(f"codex command not found. Run `codex resume {session_id}` manually.")
        return 1
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of sessions to consider (most recent first).",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Print matching sessions without interactive selection.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not execute `codex resume`; just print the command.",
    )
    parser.add_argument(
        "--git",
        action="store_true",
        help="Include sessions from other directories that share the current Git branch.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Enable deleting sessions from the interactive picker (press d).",
    )
    return parser.parse_args()


def detect_current_git_context(path: Path) -> Optional[GitContext]:
    metadata = detect_git_metadata(str(path))
    if not metadata.branch and not metadata.repository:
        return None
    return metadata


def main() -> int:
    args = parse_args()
    current_dir = Path(os.getcwd()).resolve()

    if args.delete and args.plain:
        print("Deletion is only supported in interactive mode.", file=sys.stderr)
        return 1

    git_context: Optional[GitContext] = None
    require_git_lookup = args.git

    if args.git:
        git_context = detect_current_git_context(current_dir)
        if git_context is None:
            print(
                "Warning: Unable to determine Git branch; falling back to path-based matching.",
                file=sys.stderr,
            )
            require_git_lookup = False

    summaries = gather_summaries(
        current_dir=current_dir,
        limit=args.limit,
        git_context=git_context,
        require_git_lookup=require_git_lookup,
    )

    if not summaries:
        print("No sessions found for this directory.")
        return 0

    if args.plain or not (sys.stdin.isatty() and sys.stdout.isatty()):
        for summary in summaries:
            print(format_summary_line(summary))
        return 0

    def delete_session(summary: SessionSummary) -> tuple[bool, str]:
        if not summary.file_path.exists():
            return False, "Session file already removed."
        try:
            summary.file_path.unlink()
        except OSError as exc:
            return False, f"Failed to delete: {exc}"
        return True, f"Deleted session {summary.session_id}"

    selection = interactive_select(
        summaries,
        allow_delete=args.delete,
        delete_handler=delete_session,
    )

    if selection is None:
        return 0

    command = f"codex resume {selection.session_id}"

    if args.no_resume:
        print(command)
        return 0

    exit_code = run_codex_resume(selection.session_id)
    if exit_code != 0:
        print(command)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
