"""Package allowlisted source and preinstalled Linux ARM64 dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = {"agent", "app", "tools", "policy", "evidence", "examples"}
SOURCE_FILES = {"agentcore_app.py", "LICENSE"}


def build(dependencies: Path, output: Path) -> dict:
    if not dependencies.is_dir():
        raise ValueError("Install Linux ARM64 dependencies before building the archive.")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = {}
    for path in sorted(dependencies.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(dependencies).as_posix()
        if path.name.startswith(".env") or path.is_symlink():
            raise ValueError("Unexpected sensitive file or link in dependencies.")
        files[relative] = path
    for name in tracked:
        if name and (name.split("/")[0] in SOURCE_DIRS or name in SOURCE_FILES):
            path = ROOT / name
            if path.is_symlink():
                raise ValueError("Source symlinks are not supported.")
            if name in files:
                raise ValueError(f"Source/dependency collision: {name}")
            files[name] = path
    if "agentcore_app.py" not in files:
        raise ValueError("Stage the entrypoint before building.")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip())
    info = {
        "source_commit": revision,
        "working_tree_dirty": dirty,
        "runtime": "PYTHON_3_13",
        "architecture": "arm64",
        "source": "synthetic-only",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
        archive.writestr("BUILD_INFO.json", json.dumps(info, indent=2) + "\n")
    if output.stat().st_size > 250 * 1024 * 1024:
        raise ValueError("Deployment ZIP exceeds the AgentCore 250 MB limit.")
    with output.open("rb") as built:
        digest = hashlib.file_digest(built, "sha256").hexdigest()
    return {
        **info,
        "file_count": len(files) + 1,
        "bytes": output.stat().st_size,
        "sha256": digest,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/evidencepilot-agentcore.zip")
    args = parser.parse_args()
    print(json.dumps(build(args.dependencies, args.output), indent=2))
