"""Reject non-private commit identities and known local-only tracked files.

This narrow publication guard does not replace a secret scan or an IP review.
It never prints a rejected email address or reads credential file contents.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def private_identity(address: str) -> bool:
    address = address.strip().lower()
    return address == "noreply@github.com" or bool(
        re.fullmatch(
            r"(?:\d+\+)?[a-z0-9][a-z0-9-]*(?:\[bot\])?@users\.noreply\.github\.com", address
        )
    )


def local_only_file(name: str) -> bool:
    path = PurePosixPath(name.lower())
    filename = path.name
    return (
        bool(set(path.parts) & {".aws", ".git", "out", "build", ".venv"})
        or any(part.startswith(".venv-") for part in path.parts)
        or (filename.startswith(".env") and filename != ".env.example")
        or filename.endswith((".sqlite3", ".bundle", ".tar.gz", ".pem", ".key"))
        or ".sqlite3-" in filename
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if git(root, "rev-parse", "--is-shallow-repository").strip() != "false":
        print("Publication check needs complete history; use checkout fetch-depth: 0.")
        return 1
    records = git(root, "log", "--all", "--format=%H%x00%ae%x00%ce").splitlines()
    if not records:
        print("Publication check needs at least one commit.")
        return 1
    rejected_identities = 0
    for record in records:
        _, author, committer = record.split("\0")
        rejected_identities += int(not private_identity(author))
        rejected_identities += int(not private_identity(committer))
    tracked = [name for name in git(root, "ls-files", "-z").split("\0") if name]
    rejected_paths = sum(local_only_file(name) for name in tracked)
    if rejected_identities or rejected_paths:
        print(
            f"Publication guard failed: {rejected_identities} non-private identity fields; "
            f"{rejected_paths} local-only tracked paths. Values are not displayed."
        )
        return 1
    print(f"Publication guard passed: {len(records)} commits and {len(tracked)} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
